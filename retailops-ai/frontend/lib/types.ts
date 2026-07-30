/**
 * Mirrors retailops-ai/api/agent.py::AgentQueryResponse exactly --
 * kept as a plain TypeScript interface (no codegen) since this is the
 * only cross-service contract the frontend currently depends on.
 * Fields beyond what F1's chat page reads (answer, conversation_id,
 * errors) are included now because they're real, already-returned data
 * this page's own /api/agent/query proxy passes through unmodified --
 * F3 (live execution graph) and F4 (citation drill-down) will read
 * tool_ledger/serving/provenance_map from the same response shape.
 */
export interface ToolLedgerEntry {
  tool_call_id: string;
  tool_name: string;
  status: string;
  latency_ms: number | null;
  agent: string;
}

export interface ServingModel {
  provider: string;
  model: string;
}

export interface AgentQueryResponse {
  execution_id: string;
  conversation_id: string;
  status: string;
  answer: string | null;
  plan: string | null;
  agent_results: Record<string, string>;
  tool_ledger: ToolLedgerEntry[];
  provenance_map: Record<string, string>;
  replan_rounds: number;
  citation_attempts: number;
  errors: string[];
  total_tokens: number | null;
  serving: Record<string, ServingModel>;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

/**
 * Mirrors orchestration/executor.py::run_execution_streaming()'s own
 * documented event shapes exactly (see that function's docstring) --
 * the SSE path api/agent.py's POST /agent/query serves when the
 * request carries Accept: text/event-stream.
 */
export interface TokenEvent {
  type: "token";
  node: string;
  text: string;
}

export interface AgentCompletedEvent {
  type: "agent_completed";
  agent: string;
  output: string;
  provider: string | null;
  model: string | null;
  duration_ms: number | null;
  iteration: number;
  tool_names: string[];
}

export interface ReplanJudgementEvent {
  type: "replan_judgement";
  iteration: number;
  sufficient: boolean;
  missing: string[];
  next_action: string;
  agents_to_retry: string[];
}

export interface CitationFailureDetail {
  token: string;
  value: number;
  reason: string;
}

export interface CitationCheckEvent {
  type: "citation_check";
  attempt: number;
  passed: boolean;
  failures: CitationFailureDetail[];
}

export interface ErrorEvent {
  type: "error";
  detail: string;
  error_id?: string;
}

/** The exact AgentQueryResponse field shape, plus the SSE envelope's
 * own "type" discriminant -- yielded exactly once, last.
 */
export type DoneEvent = AgentQueryResponse & { type: "done" };

export type AgentStreamEvent =
  | TokenEvent
  | AgentCompletedEvent
  | ReplanJudgementEvent
  | CitationCheckEvent
  | ErrorEvent
  | DoneEvent;
