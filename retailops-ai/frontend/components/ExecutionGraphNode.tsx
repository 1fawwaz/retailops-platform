import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { NodeStatus } from "@/lib/executionGraph";

export interface ExecutionGraphNodeData {
  agentName: string;
  status: NodeStatus;
  durationMs: number | null;
  toolNames: string[];
  round: number;
  [key: string]: unknown;
}

/** docs/DESIGN-SPEC.md §5 "Execution graph" node rules:
 *   idle       -- hairline border
 *   running    -- accent border + accent-dim fill
 *   complete   -- hairline-hi border
 *   error      -- danger border
 *   replanned  -- dashed border, 60% opacity
 * Content: agent name (sans), duration in ms (mono), tool name (mono).
 * Status is carried by border style/opacity, never by fill hue alone --
 * the status word itself is always rendered as text too (§5's
 * provenance-badge rule: "a badge that communicates only by color is a
 * bug" applies here by the same logic).
 */
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
      return "border-(--color-accent)";
    case "complete":
      return "border-(--color-hairline-hi)";
    case "error":
      return "border-(--color-danger)";
    case "replanned":
      return "border-(--color-hairline) border-dashed";
    case "idle":
    default:
      return "border-(--color-hairline)";
  }
}

export function ExecutionGraphNode({ data }: NodeProps & { data: ExecutionGraphNodeData }) {
  const { agentName, status, durationMs, toolNames, round } = data;
  return (
    <div
      className={`w-[180px] rounded-[6px] border bg-(--color-surface) px-3 py-2 transition-colors duration-150 ${borderClass(status)} ${
        status === "replanned" ? "opacity-60" : ""
      } ${status === "running" ? "bg-(--color-accent-dim)" : ""}`}
    >
      <Handle type="target" position={Position.Left} className="opacity-0" />
      <Handle type="source" position={Position.Right} className="opacity-0" />
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-medium text-(--color-text-hi)">
          {agentName}
          {round > 1 ? <span className="text-(--color-text-mid)"> · r{round}</span> : null}
        </span>
        <span
          className={`text-[11px] uppercase tracking-[0.04em] ${
            status === "error" ? "text-(--color-danger)" : "text-(--color-text-mid)"
          }`}
        >
          {STATUS_LABEL[status]}
        </span>
      </div>
      <div className="mt-1 flex items-center justify-between gap-2 font-mono text-[12px] text-(--color-text-mid)">
        <span data-numeric>{durationMs !== null ? `${durationMs}ms` : "—"}</span>
        <span className="truncate text-right" title={toolNames.join(", ") || undefined}>
          {toolNames.length > 0 ? toolNames.join(", ") : "—"}
        </span>
      </div>
    </div>
  );
}
