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

/** Task F4 ("citation drill-down"): where a numeric token in `answer`
 * resolves to. `tool_call_id` is null only for a token with no
 * grounded match anywhere -- docs/DESIGN-SPEC.md's own "MISSING
 * SOURCE" case; structurally unreachable on a real answer (the
 * citation validator already rejects any draft containing one before
 * it's ever returned), kept in the type honestly rather than assumed
 * away.
 */
export interface CitationEntry {
  token: string;
  value: number;
  tool_call_id: string | null;
  tool_name: string | null;
  agent: string | null;
  field_name: string | null;
  provenance: string | null;
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
  citations: CitationEntry[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: CitationEntry[];
  executionId?: string;
}

/** Mirrors retailops-ai/api/agent.py::ToolCallEntry /
 * ExecutionTraceResponse -- GET /agent/execution/{id}'s own shape, the
 * "deeper, fully persisted trace" a citation chip's provenance drawer
 * reads the matching raw tool response from.
 */
export interface ToolCallEntry {
  tool_call_id: string;
  agent_step_id: number | null;
  tool_name: string;
  args: Record<string, unknown> | null;
  raw_response: unknown;
  provenance_map: Record<string, string> | null;
  latency_ms: number | null;
  status: string;
  created_at: string;
}

export interface ExecutionTraceResponse {
  execution_id: string;
  conversation_id: string | null;
  query: string;
  status: string;
  plan: Record<string, unknown> | null;
  final_answer: string | null;
  provenance_map: Record<string, unknown> | null;
  errors: Record<string, unknown> | null;
  budgets: Record<string, unknown> | null;
  total_tokens: number | null;
  started_at: string;
  completed_at: string | null;
  agent_steps: unknown[];
  tool_calls: ToolCallEntry[];
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
