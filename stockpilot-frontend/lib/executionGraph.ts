import type { AgentStreamEvent } from "./types";

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
