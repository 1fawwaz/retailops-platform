"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ProvenanceBadge } from "./ProvenanceBadge";
import { formatCurrencyPrecise } from "../../lib/format";
import { ProvenanceDrawer } from "../ai-sidebar/ProvenanceDrawer";
import type { CitationEntry } from "../../lib/types";

export interface Recommendation {
  id: string;
  execution_id: string;
  sku: string | null;
  action: string;
  priority: "critical" | "high" | "medium" | "low";
  reason: string;
  revenue_at_risk: number;
  inventory_cost: number;
  confidence: number;
  risk_if_ignored: string;
  evidence: string[];
  status?: "pending" | "accepted" | "rejected" | "snoozed";
  created_at: string;
}

export interface RecommendationCardProps {
  recommendation: Recommendation;
  onDecision?: (id: string, decision: "accept" | "reject" | "snooze", timestamp: string) => void;
}

const PRIORITY_STYLES: Record<Recommendation["priority"], string> = {
  critical: "bg-red-500/10 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-400 dark:border-red-800",
  high: "bg-amber-500/10 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800",
  medium: "bg-blue-500/10 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-800",
  low: "bg-zinc-500/10 text-zinc-700 border-zinc-200 dark:bg-zinc-800/40 dark:text-zinc-400 dark:border-zinc-700",
};

export function RecommendationCard({ recommendation, onDecision }: RecommendationCardProps) {
  const router = useRouter();
  const [status, setStatus] = useState<Recommendation["status"]>(recommendation.status || "pending");
  const [openCitation, setOpenCitation] = useState<CitationEntry | null>(null);

  function handleAction(decision: "accept" | "reject" | "snooze") {
    const timestamp = new Date().toISOString();
    const newStatus = decision === "accept" ? "accepted" : decision === "reject" ? "rejected" : "snoozed";
    setStatus(newStatus);
    if (onDecision) {
      onDecision(recommendation.id, decision, timestamp);
    }
  }

  function handleNavigation() {
    const act = recommendation.action.toLowerCase();
    if (recommendation.sku && (act.includes("safety stock") || act.includes("dead stock") || act.includes("slow mover") || act.includes("replenish") || act.includes("stockout") || act.includes("reorder"))) {
      router.push(`/inventory/${recommendation.sku}`);
    } else if (act.includes("reorder") || act.includes("purchase") || act.includes("order")) {
      router.push("/purchase-orders");
    } else if (act.includes("forecast") || act.includes("demand") || act.includes("predict")) {
      router.push("/forecasts");
    } else if (act.includes("revenue") || act.includes("profit") || act.includes("margin") || act.includes("turnover") || act.includes("abc")) {
      router.push("/analytics");
    } else {
      router.push("/reports");
    }
  }

  return (
    <div className="flex flex-col justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-sm transition-all hover:border-[var(--color-border-hover)]">
      <div>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-semibold uppercase tracking-wider ${
                PRIORITY_STYLES[recommendation.priority] || PRIORITY_STYLES.medium
              }`}
            >
              {recommendation.priority}
            </span>
            {recommendation.sku && (
              <button
                type="button"
                onClick={handleNavigation}
                className="font-mono text-xs text-[var(--color-text-dim)] hover:underline hover:text-[var(--color-text-high)] text-left"
              >
                SKU: {recommendation.sku}
              </button>
            )}
          </div>
          <ProvenanceBadge provenance="predicted" />
        </div>

        {/* Clicking Recommendation title / action triggers navigation */}
        <button
          type="button"
          onClick={handleNavigation}
          className="mt-2 block w-full text-left font-medium text-[var(--color-text-high)] hover:underline hover:text-[var(--color-accent)] text-sm"
        >
          {recommendation.action}
        </button>

        <p className="mt-1 text-xs text-[var(--color-text-mid)]">{recommendation.reason}</p>

        <div className="mt-3 grid grid-cols-2 gap-2 rounded bg-[var(--color-canvas)] p-2.5 text-xs">
          <div>
            <span className="text-[var(--color-text-dim)]">Revenue at Risk: </span>
            <span className="font-mono font-medium text-[var(--color-text-high)]">
              {formatCurrencyPrecise(recommendation.revenue_at_risk)}
            </span>
          </div>
          <div>
            <span className="text-[var(--color-text-dim)]">Inventory Cost: </span>
            <span className="font-mono font-medium text-[var(--color-text-high)]">
              {formatCurrencyPrecise(recommendation.inventory_cost)}
            </span>
          </div>
          <div>
            <span className="text-[var(--color-text-dim)]">Confidence: </span>
            <span className="font-mono font-medium text-[var(--color-text-high)]">
              {Math.round(recommendation.confidence * 100)}%
            </span>
          </div>
          <div>
            <span className="text-[var(--color-text-dim)]">Risk if Ignored: </span>
            <span className="font-medium text-[var(--color-text-high)]">{recommendation.risk_if_ignored}</span>
          </div>
        </div>

        {/* Verified ToolCall citations */}
        {recommendation.evidence && recommendation.evidence.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-[var(--color-text-dim)]">Citations:</span>
            {recommendation.evidence.map((toolCallId, idx) => (
              <button
                key={toolCallId}
                type="button"
                onClick={() =>
                  setOpenCitation({
                    token: `TC-${idx + 1}`,
                    value: 0,
                    tool_call_id: toolCallId,
                    tool_name: null,
                    agent: "decision",
                    field_name: "evidence",
                    provenance: "predicted",
                  })
                }
                className="rounded bg-[var(--color-canvas)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--color-text-high)] border border-[var(--color-border)] hover:bg-[var(--color-border)] transition-colors"
                title={`ToolCall ${toolCallId}`}
              >
                [TC-{idx + 1}]
              </button>
            ))}
          </div>
        )}

        <div className="mt-2 text-[10px] font-mono text-[var(--color-text-dim)]">
          <div>Request ID: {recommendation.execution_id}</div>
          <div>Timestamp: {new Date(recommendation.created_at).toLocaleString()}</div>
        </div>
      </div>

      {/* Action Buttons */}
      <div>
        {status === "pending" ? (
          <div className="mt-3 flex items-center gap-2 pt-1">
            <button
              type="button"
              onClick={() => handleAction("accept")}
              className="flex-1 rounded border border-emerald-600/30 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-950/30 dark:text-emerald-300"
            >
              Accept
            </button>
            <button
              type="button"
              onClick={() => handleAction("snooze")}
              className="flex-1 rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1 text-xs font-semibold text-[var(--color-text-mid)] hover:bg-[var(--color-canvas)]"
            >
              Snooze
            </button>
            <button
              type="button"
              onClick={() => handleAction("reject")}
              className="flex-1 rounded border border-rose-600/30 bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-700 hover:bg-rose-100 dark:bg-rose-950/30 dark:text-rose-300"
            >
              Reject
            </button>
          </div>
        ) : (
          <div className="mt-3 flex items-center justify-between border-t border-[var(--color-border)] pt-2 text-xs text-[var(--color-text-dim)]">
            <span>Status: <strong className="capitalize text-[var(--color-text-high)]">{status}</strong></span>
            <button
              type="button"
              onClick={() => setStatus("pending")}
              className="text-[11px] underline hover:text-[var(--color-text-high)]"
            >
              Change
            </button>
          </div>
        )}
      </div>

      {/* Provenance Drawer Dialog */}
      {openCitation && (
        <ProvenanceDrawer
          key={openCitation.tool_call_id}
          citation={openCitation}
          executionId={recommendation.execution_id}
          onClose={() => setOpenCitation(null)}
        />
      )}
    </div>
  );
}
