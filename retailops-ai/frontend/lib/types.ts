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
