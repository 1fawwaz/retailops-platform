"use client";

import { useEffect, useState } from "react";
import type { CitationEntry, ExecutionTraceResponse, ToolCallEntry } from "@/lib/types";

type FetchState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; toolCall: ToolCallEntry | null };

/** docs/DESIGN-SPEC.md §5 "Citation chip": "Click opens the provenance
 * drawer." An overlay (the one place box-shadow is permitted, §4), not
 * a card -- fetches GET /agent/execution/{id} once per open and shows
 * the specific tool call this citation resolved to: its raw response
 * verbatim, so "the grounding architecture [is] provable in one click"
 * (BUILD-SPEC's own F4 wording), not summarized or reformatted away
 * from what the tool actually returned.
 */
export function ProvenanceDrawer({
  citation,
  executionId,
  onClose,
}: {
  citation: CitationEntry;
  executionId: string;
  onClose: () => void;
}) {
  // No synchronous setState-in-effect reset here (react-hooks/set-state-in-effect
  // correctly flags that as cascading-render-prone) -- a genuinely new
  // citation gets a fresh mount instead, via the `key` prop the caller
  // (app/chat/page.tsx) puts on this component, so useState's own
  // initializer already covers that case. The Retry button resets to
  // "loading" itself, in its own event handler, not here.
  const [state, setState] = useState<FetchState>({ status: "loading" });
  // Bumped by the Retry button -- included in the effect's own
  // dependency array below so a retry actually re-runs the fetch.
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;

    fetch(`/api/agent/execution/${executionId}`, { headers: { Accept: "application/json" } })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Request failed (${response.status}).`);
        }
        return (await response.json()) as ExecutionTraceResponse;
      })
      .then((trace) => {
        if (cancelled) {
          return;
        }
        const toolCall =
          trace.tool_calls.find((call) => call.tool_call_id === citation.tool_call_id) ?? null;
        setState({ status: "ready", toolCall });
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        setState({
          status: "error",
          message: error instanceof Error ? error.message : "Could not load the trace.",
        });
      });

    return () => {
      cancelled = true;
    };
  }, [executionId, citation.tool_call_id, retryCount]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <div
        role="dialog"
        aria-label="Citation provenance"
        onClick={(event) => event.stopPropagation()}
        className="flex h-full w-full max-w-md flex-col overflow-y-auto border-l border-(--color-hairline) bg-(--color-surface) shadow-[0_0_32px_rgba(0,0,0,0.4)]"
      >
        <div className="flex items-center justify-between border-b border-(--color-hairline) px-5 py-4">
          <h2 className="text-[16px] font-medium text-(--color-text-hi)">Provenance</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-[6px] px-2 py-1 text-[13px] text-(--color-text-mid) transition-colors duration-150 hover:text-(--color-text-hi) focus-visible:outline focus-visible:outline-2 focus-visible:outline-(--color-accent)"
          >
            Close
          </button>
        </div>

        <div className="flex flex-1 flex-col gap-4 px-5 py-4">
          <div>
            <p className="text-[11px] text-(--color-text-mid) uppercase tracking-[0.04em]">
              Cited value
            </p>
            <p className="mt-1 font-mono text-[20px] text-(--color-text-hi)" data-numeric>
              {citation.token}
            </p>
          </div>

          {state.status === "loading" && (
            <div className="flex flex-col gap-2" aria-busy="true">
              <div className="h-4 w-2/3 animate-pulse rounded-[6px] bg-(--color-raised)" />
              <div className="h-4 w-1/2 animate-pulse rounded-[6px] bg-(--color-raised)" />
              <div className="h-32 w-full animate-pulse rounded-[6px] bg-(--color-raised)" />
            </div>
          )}

          {state.status === "error" && (
            <div className="flex flex-col gap-2">
              <p className="text-[14px] text-(--color-danger)">{state.message}</p>
              <button
                type="button"
                onClick={() => {
                  setState({ status: "loading" });
                  setRetryCount((count) => count + 1);
                }}
                className="self-start rounded-[6px] border border-(--color-hairline) px-3 py-1.5 text-[13px] text-(--color-text-hi) transition-colors duration-150 hover:border-(--color-hairline-hi)"
              >
                Retry
              </button>
            </div>
          )}

          {state.status === "ready" && state.toolCall === null && (
            <p className="text-[14px] text-(--color-text-mid)">
              This execution&rsquo;s persisted trace no longer contains a matching tool call.
            </p>
          )}

          {state.status === "ready" && state.toolCall !== null && (
            <>
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-[13px]">
                <dt className="text-(--color-text-mid)">Tool</dt>
                <dd className="font-mono text-(--color-text-hi)">{state.toolCall.tool_name}</dd>

                <dt className="text-(--color-text-mid)">Agent</dt>
                <dd className="text-(--color-text-hi)">{citation.agent ?? "—"}</dd>

                <dt className="text-(--color-text-mid)">Field</dt>
                <dd className="font-mono text-(--color-text-hi)">{citation.field_name ?? "—"}</dd>

                <dt className="text-(--color-text-mid)">Provenance</dt>
                <dd className="text-(--color-text-hi)">{citation.provenance ?? "—"}</dd>

                <dt className="text-(--color-text-mid)">Status</dt>
                <dd className="text-(--color-text-hi)">{state.toolCall.status}</dd>

                <dt className="text-(--color-text-mid)">Latency</dt>
                <dd className="font-mono text-(--color-text-hi)" data-numeric>
                  {state.toolCall.latency_ms !== null ? `${state.toolCall.latency_ms}ms` : "—"}
                </dd>
              </dl>

              <div>
                <p className="mb-1.5 text-[11px] text-(--color-text-mid) uppercase tracking-[0.04em]">
                  Raw tool response
                </p>
                <pre className="overflow-x-auto rounded-[6px] border border-(--color-hairline) bg-(--color-canvas) p-3 font-mono text-[12px] leading-[1.45] text-(--color-text-hi)">
                  {JSON.stringify(state.toolCall.raw_response, null, 2)}
                </pre>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
