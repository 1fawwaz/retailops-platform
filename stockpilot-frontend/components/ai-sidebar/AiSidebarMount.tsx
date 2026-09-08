"use client";

import { useRef, useState, type FormEvent } from "react";
import { parseSSEStream } from "../../lib/sse";
import type { ChatMessage, CitationEntry } from "../../lib/types";
import {
  applyStreamEvent,
  initialExecutionGraphState,
  type ExecutionGraphState,
} from "../../lib/executionGraph";
import { ExecutionGraph } from "./ExecutionGraph";
import { CitationText } from "./CitationText";
import { ProvenanceDrawer } from "./ProvenanceDrawer";
import { getToken } from "../../lib/auth/token";

import { getAiBaseUrl } from "../../lib/api/aiClient";

export function AiSidebarMount() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamingText, setStreamingText] = useState("");
  const [graph, setGraph] = useState<ExecutionGraphState | null>(null);
  const [activeTab, setActiveTab] = useState<"chat" | "graph">("chat");
  const [openCitation, setOpenCitation] = useState<{
    citation: CitationEntry;
    executionId: string;
  } | null>(null);
  const conversationId = useRef<string | null>(null);
  const abortController = useRef<AbortController | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const query = input.trim();
    if (!query || isSending) {
      return;
    }

    const token = getToken();
    if (!token) {
      setError("Please log in to use the AI Copilot.");
      return;
    }

    setError(null);
    setMessages((current) => [...current, { role: "user", content: query }]);
    setInput("");
    setStreamingText("");
    setGraph(initialExecutionGraphState());
    setIsSending(true);

    const controller = new AbortController();
    abortController.current = controller;
    // Step 3 / Amendment 1: 150s timeout ceiling until Step 7 optimizations are verified
    const timeoutId = setTimeout(() => {
      controller.abort();
    }, 150000);

    try {
      const response = await fetch(`${getAiBaseUrl()}/agent/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          query,
          conversation_id: conversationId.current,
        }),
        signal: controller.signal,
      });

      if (response.status === 401) {
        setError("Your session has expired. Please refresh the page and log in again.");
        setIsSending(false);
        return;
      }

      if (!response.ok || !response.body) {
        const responseBody = (await response.json().catch(() => null)) as {
          detail?: string;
        } | null;
        setError(responseBody?.detail ?? `Request failed (${response.status}).`);
        setIsSending(false);
        return;
      }

      let finalAnswer: string | null = null;
      let finalCitations: CitationEntry[] = [];
      let finalExecutionId: string | null = null;
      let sawError = false;

      for await (const streamEvent of parseSSEStream(response.body)) {
        setGraph((current) => (current ? applyStreamEvent(current, streamEvent) : current));

        switch (streamEvent.type) {
          case "token":
            if (streamEvent.node === "decision" && !finalAnswer) {
              setStreamingText((current) => current + streamEvent.text);
            }
            break;
          case "citation_check":
            if (!streamEvent.passed && !finalAnswer) {
              setStreamingText("");
            }
            break;
          case "error":
            // Step 6: If finalAnswer has already arrived, do not overwrite/suppress it with a late stream error
            if (!finalAnswer) {
              sawError = true;
              setError(streamEvent.detail);
            }
            break;
          case "done":
            finalAnswer = streamEvent.answer;
            finalCitations = streamEvent.citations;
            finalExecutionId = streamEvent.execution_id;
            conversationId.current = streamEvent.conversation_id;
            break;
          default:
            break;
        }
      }

      if (finalAnswer && finalAnswer.trim()) {
        // Step 6: Valid final answer locked -- render assistant message even if stream closed afterwards
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            content: finalAnswer,
            citations: finalCitations,
            executionId: finalExecutionId ?? undefined,
          },
        ]);
        setError(null);
      } else if (!sawError) {
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            content: "No answer was produced for this query.",
            citations: finalCitations,
            executionId: finalExecutionId ?? undefined,
          },
        ]);
      }
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        setError("Could not reach the AI service.");
      } else if (!isSending) {
        setError("Request timed out (150s exceeded).");
      }
    } finally {
      clearTimeout(timeoutId);
      setStreamingText("");
      setIsSending(false);
      abortController.current = null;
    }
  }

  function handleStop(): void {
    abortController.current?.abort();
  }

  return (
    <>
      {/* Floating Toggle Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-[var(--color-accent)] text-[var(--color-canvas)] shadow-lg transition-transform hover:scale-105 active:scale-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
        aria-label="Toggle AI Copilot"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
          className="h-6 w-6"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-3.658A8.967 8.967 0 0 1 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z"
          />
        </svg>
      </button>

      {/* Slide-out Sidebar Panel */}
      {isOpen && (
        <aside
          className="fixed bottom-0 right-0 top-0 z-50 flex h-full w-[450px] flex-col border-l border-[var(--color-border)] bg-[var(--color-surface)] shadow-2xl transition-all duration-300 ease-in-out"
          style={{ maxWidth: "100%" }}
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-4">
            <div className="flex items-baseline gap-2">
              <h3 className="text-base font-semibold text-[var(--color-text-high)]">RetailOps AI Copilot</h3>
              <span className="font-mono text-[10px] text-[var(--color-text-mid)] font-semibold">
                IN FMCG · ₹
              </span>
            </div>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="rounded px-2 py-1 text-xs font-semibold text-[var(--color-text-mid)] hover:bg-[var(--color-canvas)] hover:text-[var(--color-text-high)]"
            >
              Close
            </button>
          </div>

          {/* Navigation Tabs */}
          <div className="flex border-b border-[var(--color-border)] bg-[var(--color-canvas)] text-xs">
            <button
              type="button"
              onClick={() => setActiveTab("chat")}
              className={`flex-1 py-3 text-center font-medium transition-colors ${
                activeTab === "chat"
                  ? "border-b-2 border-[var(--color-accent)] text-[var(--color-text-high)]"
                  : "text-[var(--color-text-mid)] hover:text-[var(--color-text-high)]"
              }`}
            >
              Chat Assistant
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("graph")}
              className={`flex-1 py-3 text-center font-medium transition-colors ${
                activeTab === "graph"
                  ? "border-b-2 border-[var(--color-accent)] text-[var(--color-text-high)]"
                  : "text-[var(--color-text-mid)] hover:text-[var(--color-text-high)]"
              }`}
            >
              Execution Trace {graph ? `(${graph.nodes.filter(n => n.status === "complete").length}/${graph.nodes.length})` : ""}
            </button>
          </div>

          {/* Body Content */}
          <div className="flex flex-1 flex-col overflow-hidden">
            {activeTab === "chat" ? (
              <div className="flex flex-1 flex-col overflow-hidden">
                {/* Messages Panel */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {messages.length === 0 && !isSending && (
                    <div className="rounded-lg bg-[var(--color-canvas)] p-4 text-xs leading-relaxed text-[var(--color-text-mid)]">
                      <p className="font-semibold text-[var(--color-text-high)] mb-1">Welcome to RetailOps AI!</p>
                      Ask me anything about inventory, demand forecasting, reordering thresholds, or business metrics. Try asking:
                      <ul className="mt-2 list-inside list-disc space-y-1 font-medium text-[var(--color-text-high)]">
                        <li>&quot;Which SKUs are at risk of stockout?&quot;</li>
                        <li>&quot;What is the inventory valuation by category?&quot;</li>
                        <li>&quot;Show me the demand forecast for the next 14 days.&quot;</li>

                      </ul>
                    </div>
                  )}

                  {messages.map((msg, idx) => (
                    <div
                      key={idx}
                      className={`flex flex-col ${
                        msg.role === "user" ? "items-end" : "items-start"
                      }`}
                    >
                      <div
                        className={`max-w-[90%] rounded-lg px-3 py-2 text-xs leading-relaxed ${
                          msg.role === "user"
                            ? "bg-[var(--color-accent)] text-[var(--color-canvas)]"
                            : "border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-high)]"
                        }`}
                      >
                        {msg.role === "assistant" && msg.citations && msg.executionId ? (
                          <CitationText
                            text={msg.content}
                            citations={msg.citations}
                            onOpenCitation={(citation) =>
                              setOpenCitation({ citation, executionId: msg.executionId! })
                            }
                          />
                        ) : (
                          msg.content
                        )}
                      </div>
                    </div>
                  ))}

                  {isSending && (
                    <div className="flex flex-col items-start">
                      <div className="max-w-[90%] rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-xs leading-relaxed text-[var(--color-text-high)] italic">
                        {streamingText || "Thinking..."}
                      </div>
                    </div>
                  )}

                  {error && (
                    <div role="alert" className="text-xs text-[var(--color-danger)] px-2">
                      {error}
                    </div>
                  )}
                </div>

                {/* Input form */}
                <form onSubmit={handleSubmit} className="border-t border-[var(--color-border)] p-4 bg-[var(--color-canvas)] flex items-center gap-2">
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ask a question..."
                    disabled={isSending}
                    className="flex-1 rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-xs text-[var(--color-text-high)] placeholder-[var(--color-text-mid)] outline-none focus:border-[var(--color-accent)] disabled:opacity-60"
                  />
                  {isSending ? (
                    <button
                      type="button"
                      onClick={handleStop}
                      className="rounded bg-[var(--color-danger)] px-4 py-2 text-xs font-semibold text-[var(--color-canvas)] hover:opacity-90"
                    >
                      Stop
                    </button>
                  ) : (
                    <button
                      type="submit"
                      disabled={!input.trim()}
                      className="rounded bg-[var(--color-accent)] px-4 py-2 text-xs font-semibold text-[var(--color-canvas)] hover:opacity-90 disabled:opacity-45"
                    >
                      Send
                    </button>
                  )}
                </form>
              </div>
            ) : (
              <div className="flex flex-1 flex-col overflow-hidden p-4">
                {graph ? (
                  <div className="flex flex-1 flex-col gap-3 overflow-hidden">
                    {graph.replanNote && (
                      <div className="rounded bg-[var(--color-accent-dim)] px-3 py-2 text-xs text-[var(--color-text-high)] font-medium">
                        {graph.replanNote}
                      </div>
                    )}
                    {graph.citationNote && (
                      <div className="rounded bg-amber-500/10 px-3 py-2 text-xs text-amber-700 font-medium">
                        {graph.citationNote}
                      </div>
                    )}
                    <div className="flex-1 overflow-hidden">
                      <ExecutionGraph graph={graph} />
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-1 items-center justify-center text-xs text-[var(--color-text-mid)]">
                    Start a query to trace execution in real-time.
                  </div>
                )}
              </div>
            )}
          </div>
        </aside>
      )}

      {/* Provenance Drawer Dialog */}
      {openCitation && (
        <ProvenanceDrawer
          key={`${openCitation.executionId}-${openCitation.citation.tool_call_id}`}
          citation={openCitation.citation}
          executionId={openCitation.executionId}
          onClose={() => setOpenCitation(null)}
        />
      )}
    </>
  );
}
