import type { AgentStreamEvent } from "@/lib/types";

/**
 * Pure reducer turning the SAME SSE event stream lib/sse.ts already
 * parses for the chat page (F2) into a node/edge model for the live
 * execution graph (F3, docs/DESIGN-SPEC.md §5's "Execution graph"
 * rules). No second connection: the chat page calls
 * applyStreamEvent() once per event, alongside its own message-state
 * updates, since an SSE response body can only be consumed once.
 */

export type NodeStatus = "idle" | "running" | "complete" | "error" | "replanned";

export const RETRIEVAL_AGENTS = ["inventory", "forecast", "analytics"] as const;
type RetrievalAgent = (typeof RETRIEVAL_AGENTS)[number];

function isRetrievalAgent(name: string): name is RetrievalAgent {
  return (RETRIEVAL_AGENTS as readonly string[]).includes(name);
}

export interface GraphNode {
  id: string;
  agentName: string;
  round: number;
  status: NodeStatus;
  durationMs: number | null;
  toolNames: string[];
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
}

export interface ExecutionGraphState {
  nodes: GraphNode[];
  edges: GraphEdge[];
  replanNote: string | null;
  citationNote: string | null;
}

/** A fresh graph for a new query. Round 1's three retrieval agents are
 * pre-populated as "running" immediately -- orchestration/graph.py's
 * topology always fans out to all three unconditionally (Task 3.2), so
 * this is a known fact about the run that's about to happen, not a
 * guess; nothing else about docs/DESIGN-SPEC.md's "the LangGraph path
 * animating as the agent runs" is achievable if nodes only appear once
 * already complete. Report/Decision start "idle": the graph always
 * reaches them eventually, but not until at least one replan_judgement
 * has fired, so they wait for that signal rather than being marked
 * "running" prematurely.
 */
export function initialExecutionGraphState(): ExecutionGraphState {
  const nodes: GraphNode[] = [
    { id: "planner", agentName: "planner", round: 1, status: "running", durationMs: null, toolNames: [] },
    ...RETRIEVAL_AGENTS.map(
      (name): GraphNode => ({
        id: `${name}-r1`,
        agentName: name,
        round: 1,
        status: "running",
        durationMs: null,
        toolNames: [],
      }),
    ),
    { id: "report", agentName: "report", round: 1, status: "idle", durationMs: null, toolNames: [] },
    { id: "decision", agentName: "decision", round: 1, status: "idle", durationMs: null, toolNames: [] },
  ];
  const edges: GraphEdge[] = [
    ...RETRIEVAL_AGENTS.map(
      (name): GraphEdge => ({ id: `planner->${name}-r1`, source: "planner", target: `${name}-r1` }),
    ),
    ...RETRIEVAL_AGENTS.map(
      (name): GraphEdge => ({ id: `${name}-r1->report`, source: `${name}-r1`, target: "report" }),
    ),
    { id: "report->decision", source: "report", target: "decision" },
  ];
  return { nodes, edges, replanNote: null, citationNote: null };
}

function nodeIdFor(agent: string, iteration: number): string {
  return isRetrievalAgent(agent) ? `${agent}-r${iteration}` : agent;
}

export function applyStreamEvent(
  state: ExecutionGraphState,
  event: AgentStreamEvent,
): ExecutionGraphState {
  switch (event.type) {
    case "agent_completed": {
      const nodeId = nodeIdFor(event.agent, event.iteration);
      return {
        ...state,
        nodes: state.nodes.map((node) => {
          if (node.id === nodeId) {
            return {
              ...node,
              status: "complete",
              durationMs: event.duration_ms,
              toolNames: event.tool_names,
            };
          }
          // Planner never emits its own agent_completed (it writes to
          // state["plan"], not state["agent_results"] --
          // orchestration/graph.py::_make_planner_node) -- the first
          // retrieval-agent completion is the earliest available proof
          // it already finished, since planner -> each retrieval agent
          // is a real graph edge (orchestration/graph.py).
          if (node.id === "planner" && node.status !== "complete") {
            return { ...node, status: "complete" };
          }
          return node;
        }),
      };
    }

    case "replan_judgement": {
      if (event.sufficient) {
        return {
          ...state,
          replanNote: null,
          nodes: state.nodes.map((node) =>
            (node.id === "report" || node.id === "decision") && node.status === "idle"
              ? { ...node, status: "running" }
              : node,
          ),
        };
      }

      // Mirrors orchestration/graph.py::_route_after_replan()'s own
      // fallback EXACTLY: insufficient but the judgement names no agent
      // (a malformed-but-plausible LLM output) still retries all three,
      // so the loop can't stall -- proven live during this task's own
      // verification: without replicating this here, a real judgement
      // with an empty agents_to_retry silently dropped that whole
      // round's node creation, orphaning its later agent_completed
      // events (no node existed for them to update) and leaving the
      // PRIOR round wrongly stuck at "complete" instead of "replanned".
      const retriedAgents =
        event.agents_to_retry.length > 0 ? event.agents_to_retry : [...RETRIEVAL_AGENTS];

      const newRound = event.iteration + 1;
      const supersededIds = new Set(
        retriedAgents.map((name) => nodeIdFor(name, event.iteration)),
      );
      const newNodes: GraphNode[] = retriedAgents.map((name) => ({
        id: nodeIdFor(name, newRound),
        agentName: name,
        round: newRound,
        status: "running",
        durationMs: null,
        toolNames: [],
      }));
      // docs/DESIGN-SPEC.md §5: "A replan appends a branch and dims what
      // it superseded. It never clears the canvas." -- the old edge into
      // report stays (report's own prose still reflects every round's
      // evidence, superseded or not), a new branch is added alongside it.
      const newEdges: GraphEdge[] = retriedAgents.flatMap((name) => [
        {
          id: `${nodeIdFor(name, event.iteration)}->${nodeIdFor(name, newRound)}`,
          source: nodeIdFor(name, event.iteration),
          target: nodeIdFor(name, newRound),
        },
        {
          id: `${nodeIdFor(name, newRound)}->report`,
          source: nodeIdFor(name, newRound),
          target: "report",
        },
      ]);

      return {
        ...state,
        replanNote: `Round ${newRound}: ${event.next_action}`,
        nodes: [
          ...state.nodes.map((node) =>
            supersededIds.has(node.id) ? { ...node, status: "replanned" as NodeStatus } : node,
          ),
          ...newNodes,
        ],
        edges: [...state.edges, ...newEdges],
      };
    }

    case "done": {
      // Rare edge case the frontend has no direct signal for: the
      // iteration budget cap (config/models.yaml's own
      // budgets.max_tool_iterations, not exposed over SSE) can be hit
      // while a judgement still says insufficient --
      // orchestration/graph.py::_route_after_replan() routes straight to
      // Report anyway, so the round this reducer speculatively created
      // from that judgement's own agents_to_retry never actually runs.
      // Once "done" fires the whole execution is over, so anything still
      // "running" here was never real -- "replanned" (superseded) is the
      // closest honest fit within docs/DESIGN-SPEC.md's fixed node-state
      // vocabulary: it WAS planned, then superseded by the cap forcing
      // the graph on to Report before it could run.
      return {
        ...state,
        nodes: state.nodes.map((node) =>
          node.status === "running" && isRetrievalAgent(node.agentName)
            ? { ...node, status: "replanned" as NodeStatus }
            : node,
        ),
      };
    }

    case "citation_check": {
      if (event.passed) {
        return { ...state, citationNote: null };
      }
      return {
        ...state,
        citationNote: `Citation check failed on attempt ${event.attempt}; Decision Engine is regenerating.`,
      };
    }

    case "error": {
      // The single best-available honest signal for "which node failed":
      // whichever nodes never got to report their own completion before
      // the stream ended. Not a claim about which one CAUSED the error.
      return {
        ...state,
        nodes: state.nodes.map((node) =>
          node.status === "running" || node.status === "idle"
            ? { ...node, status: "error" }
            : node,
        ),
      };
    }

    default:
      return state;
  }
}
