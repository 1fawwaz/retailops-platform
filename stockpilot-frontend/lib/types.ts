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

export type DoneEvent = AgentQueryResponse & { type: "done" };

export type AgentStreamEvent =
  | TokenEvent
  | AgentCompletedEvent
  | ReplanJudgementEvent
  | CitationCheckEvent
  | ErrorEvent
  | DoneEvent;
