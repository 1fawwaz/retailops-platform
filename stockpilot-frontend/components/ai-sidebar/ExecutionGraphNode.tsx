import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { NodeStatus } from "../../lib/executionGraph";

export interface ExecutionGraphNodeData {
  agentName: string;
  status: NodeStatus;
  durationMs: number | null;
  toolNames: string[];
  round: number;
  [key: string]: unknown;
}

const STATUS_LABEL: Record<NodeStatus, string> = {
  idle: "Idle",
  running: "Running",
  complete: "Complete",
  error: "Error",
  replanned: "Superseded",
};

function borderClass(status: NodeStatus): string {
  switch (status) {
    case "running":
      return "border-[var(--color-accent)]";
    case "complete":
      return "border-[var(--color-border-hover)]";
    case "error":
      return "border-[var(--color-danger)]";
    case "replanned":
      return "border-[var(--color-border)] border-dashed";
    case "idle":
    default:
      return "border-[var(--color-border)]";
  }
}

export function ExecutionGraphNode({ data }: NodeProps & { data: ExecutionGraphNodeData }) {
  const { agentName, status, durationMs, toolNames, round } = data;
  return (
    <div
      className={`w-[180px] rounded-md border bg-[var(--color-surface)] px-3 py-2 transition-colors duration-150 ${borderClass(status)} ${
        status === "replanned" ? "opacity-60" : ""
      } ${status === "running" ? "bg-[var(--color-accent-dim)]" : ""}`}
    >
      <Handle type="target" position={Position.Left} className="opacity-0" />
      <Handle type="source" position={Position.Right} className="opacity-0" />
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-medium text-[var(--color-text-high)] capitalize">
          {agentName}
          {round > 1 ? <span className="text-[var(--color-text-mid)]"> · r{round}</span> : null}
        </span>
        <span
          className={`text-[10px] font-semibold uppercase tracking-wider ${
            status === "error" ? "text-[var(--color-danger)]" : "text-[var(--color-text-mid)]"
          }`}
        >
          {STATUS_LABEL[status]}
        </span>
      </div>
      <div className="mt-1 flex items-center justify-between gap-2 font-mono text-[11px] text-[var(--color-text-mid)]">
        <span data-numeric>{durationMs !== null ? `${durationMs}ms` : "—"}</span>
        <span className="truncate text-right" title={toolNames.join(", ") || undefined}>
          {toolNames.length > 0 ? toolNames.join(", ") : "—"}
        </span>
      </div>
    </div>
  );
}
