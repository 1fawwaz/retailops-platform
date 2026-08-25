import { describe, expect, it } from "vitest";
import {
  applyStreamEvent,
  initialExecutionGraphState,
  type ExecutionGraphState,
} from "@/lib/executionGraph";
import type {
  AgentCompletedEvent,
  DoneEvent,
  ReplanJudgementEvent,
} from "@/lib/types";

function nodeStatus(state: ExecutionGraphState, id: string): string | undefined {
  return state.nodes.find((n) => n.id === id)?.status;
}

function agentCompleted(overrides: Partial<AgentCompletedEvent>): AgentCompletedEvent {
  return {
    type: "agent_completed",
    agent: "inventory",
    output: "answer",
    provider: "groq",
    model: "openai/gpt-oss-120b",
    duration_ms: 100,
    iteration: 1,
    tool_names: [],
    ...overrides,
  };
}

function replanJudgement(overrides: Partial<ReplanJudgementEvent>): ReplanJudgementEvent {
  return {
    type: "replan_judgement",
    iteration: 1,
    sufficient: true,
    missing: [],
    next_action: "proceed",
    agents_to_retry: [],
    ...overrides,
  };
}

describe("initialExecutionGraphState", () => {
  it("pre-populates planner and all three round-1 retrieval agents as running", () => {
    const state = initialExecutionGraphState();
    expect(nodeStatus(state, "planner")).toBe("running");
    expect(nodeStatus(state, "inventory-r1")).toBe("running");
    expect(nodeStatus(state, "forecast-r1")).toBe("running");
    expect(nodeStatus(state, "analytics-r1")).toBe("running");
    expect(nodeStatus(state, "report")).toBe("idle");
    expect(nodeStatus(state, "decision")).toBe("idle");
  });
});

describe("agent_completed", () => {
  it("marks the matching node complete with its duration and tool names", () => {
    let state = initialExecutionGraphState();
    state = applyStreamEvent(
      state,
      agentCompleted({ agent: "inventory", iteration: 1, duration_ms: 250, tool_names: ["get_product"] }),
    );
    const node = state.nodes.find((n) => n.id === "inventory-r1");
    expect(node?.status).toBe("complete");
    expect(node?.durationMs).toBe(250);
    expect(node?.toolNames).toEqual(["get_product"]);
  });

  it("infers planner completion from the first retrieval agent's own completion, since planner never emits its own agent_completed", () => {
    let state = initialExecutionGraphState();
    expect(nodeStatus(state, "planner")).toBe("running");
    state = applyStreamEvent(state, agentCompleted({ agent: "forecast", iteration: 1 }));
    expect(nodeStatus(state, "planner")).toBe("complete");
  });
});

describe("replan_judgement -- sufficient", () => {
  it("moves idle report/decision to running and clears the replan note", () => {
    let state = initialExecutionGraphState();
    state = { ...state, replanNote: "stale note" };
    state = applyStreamEvent(state, replanJudgement({ sufficient: true, iteration: 1 }));
    expect(nodeStatus(state, "report")).toBe("running");
    expect(nodeStatus(state, "decision")).toBe("running");
    expect(state.replanNote).toBeNull();
  });
});

describe("replan_judgement -- insufficient", () => {
  it("supersedes the named agents' current-round nodes and appends a new round", () => {
    let state = initialExecutionGraphState();
    state = applyStreamEvent(
      state,
      replanJudgement({
        sufficient: false,
        iteration: 1,
        next_action: "retry forecast with a narrower window",
        agents_to_retry: ["forecast"],
      }),
    );

    expect(nodeStatus(state, "forecast-r1")).toBe("replanned");
    expect(nodeStatus(state, "inventory-r1")).toBe("running"); // not retried, untouched
    expect(nodeStatus(state, "analytics-r1")).toBe("running");
    expect(nodeStatus(state, "forecast-r2")).toBe("running");
    expect(state.replanNote).toContain("Round 2");
    expect(state.replanNote).toContain("retry forecast");

    // "never clears the canvas" -- the old edge into report is preserved
    // alongside the new branch's own edge.
    expect(state.edges.some((e) => e.source === "forecast-r1" && e.target === "report")).toBe(true);
    expect(state.edges.some((e) => e.source === "forecast-r2" && e.target === "report")).toBe(true);
    expect(state.edges.some((e) => e.source === "forecast-r1" && e.target === "forecast-r2")).toBe(
      true,
    );
  });

  it("REGRESSION (found via live testing): falls back to all three retrieval agents when the judgement names none, matching orchestration/graph.py::_route_after_replan()'s own fallback -- without this, a real empty agents_to_retry silently dropped that round's nodes entirely and its later agent_completed events had nowhere to land", () => {
    let state = initialExecutionGraphState();
    state = applyStreamEvent(
      state,
      replanJudgement({
        sufficient: false,
        iteration: 1,
        next_action: "gather more evidence",
        agents_to_retry: [], // the real, live-observed malformed shape
      }),
    );

    // All three round-1 nodes superseded, all three round-2 nodes created --
    // not silently dropped.
    expect(nodeStatus(state, "inventory-r1")).toBe("replanned");
    expect(nodeStatus(state, "forecast-r1")).toBe("replanned");
    expect(nodeStatus(state, "analytics-r1")).toBe("replanned");
    expect(nodeStatus(state, "inventory-r2")).toBe("running");
    expect(nodeStatus(state, "forecast-r2")).toBe("running");
    expect(nodeStatus(state, "analytics-r2")).toBe("running");

    // The round-2 completions now have a real node to land on.
    state = applyStreamEvent(state, agentCompleted({ agent: "inventory", iteration: 2 }));
    expect(nodeStatus(state, "inventory-r2")).toBe("complete");
  });

  it("handles two consecutive insufficient rounds without losing the middle round (the exact live scenario that surfaced the bug above)", () => {
    let state = initialExecutionGraphState();
    state = applyStreamEvent(
      state,
      replanJudgement({ sufficient: false, iteration: 1, agents_to_retry: [] }),
    );
    state = applyStreamEvent(state, agentCompleted({ agent: "inventory", iteration: 2 }));
    state = applyStreamEvent(state, agentCompleted({ agent: "forecast", iteration: 2 }));
    state = applyStreamEvent(state, agentCompleted({ agent: "analytics", iteration: 2 }));
    state = applyStreamEvent(
      state,
      replanJudgement({ sufficient: false, iteration: 2, agents_to_retry: ["inventory"] }),
    );

    // Round 1: superseded. Round 2: inventory superseded (retried again),
    // forecast/analytics stay complete (never retried a second time).
    // Round 3: only inventory, freshly running.
    expect(nodeStatus(state, "inventory-r1")).toBe("replanned");
    expect(nodeStatus(state, "inventory-r2")).toBe("replanned");
    expect(nodeStatus(state, "forecast-r2")).toBe("complete");
    expect(nodeStatus(state, "analytics-r2")).toBe("complete");
    expect(nodeStatus(state, "inventory-r3")).toBe("running");
    expect(state.nodes.filter((n) => n.agentName === "inventory")).toHaveLength(3);
  });
});

describe("citation_check", () => {
  it("sets a note on failure and clears it on a passing attempt", () => {
    let state = initialExecutionGraphState();
    state = applyStreamEvent(state, {
      type: "citation_check",
      attempt: 1,
      passed: false,
      failures: [{ token: "42", value: 42, reason: "not_found" }],
    });
    expect(state.citationNote).toContain("attempt 1");

    state = applyStreamEvent(state, { type: "citation_check", attempt: 2, passed: true, failures: [] });
    expect(state.citationNote).toBeNull();
  });
});

describe("error", () => {
  it("marks every still-running or still-idle node as error, leaving completed nodes alone", () => {
    let state = initialExecutionGraphState();
    state = applyStreamEvent(state, agentCompleted({ agent: "inventory", iteration: 1 }));
    state = applyStreamEvent(state, { type: "error", detail: "This request took too long." });

    expect(nodeStatus(state, "inventory-r1")).toBe("complete"); // untouched
    expect(nodeStatus(state, "forecast-r1")).toBe("error");
    expect(nodeStatus(state, "analytics-r1")).toBe("error");
    expect(nodeStatus(state, "report")).toBe("error");
    expect(nodeStatus(state, "decision")).toBe("error");
  });
});

describe("done", () => {
  function doneEvent(): DoneEvent {
    return {
      type: "done",
      execution_id: "e1",
      conversation_id: "c1",
      status: "completed",
      answer: "answer",
      plan: null,
      agent_results: {},
      tool_ledger: [],
      provenance_map: {},
      replan_rounds: 1,
      citation_attempts: 1,
      errors: [],
      total_tokens: 10,
      serving: {},
      citations: [],
    };
  }

  it("resolves an orphaned speculative round (iteration cap hit while still insufficient) to replanned rather than leaving it stuck running forever", () => {
    let state = initialExecutionGraphState();
    // A judgement says insufficient and names an agent, but the cap is
    // hit server-side (invisible to the frontend) -- routing goes
    // straight to report/decision, whose OWN real completions still
    // arrive, but the speculative new round this reducer created never
    // gets a matching agent_completed.
    state = applyStreamEvent(
      state,
      replanJudgement({ sufficient: false, iteration: 1, agents_to_retry: ["inventory"] }),
    );
    state = applyStreamEvent(state, agentCompleted({ agent: "forecast", iteration: 1 }));
    state = applyStreamEvent(state, agentCompleted({ agent: "analytics", iteration: 1 }));
    state = applyStreamEvent(state, agentCompleted({ agent: "report", iteration: 1 }));
    state = applyStreamEvent(state, agentCompleted({ agent: "decision", iteration: 1 }));
    expect(nodeStatus(state, "inventory-r2")).toBe("running");

    state = applyStreamEvent(state, doneEvent());
    expect(nodeStatus(state, "inventory-r2")).toBe("replanned");
    expect(nodeStatus(state, "report")).toBe("complete"); // real completions untouched
    expect(nodeStatus(state, "decision")).toBe("complete");
  });
});
