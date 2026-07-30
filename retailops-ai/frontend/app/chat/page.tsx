"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { parseSSEStream } from "@/lib/sse";
import type { ChatMessage } from "@/lib/types";
import {
  applyStreamEvent,
  initialExecutionGraphState,
  type ExecutionGraphState,
} from "@/lib/executionGraph";
import { ExecutionGraph } from "@/components/ExecutionGraph";

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamingText, setStreamingText] = useState("");
  const [graph, setGraph] = useState<ExecutionGraphState | null>(null);
  const conversationId = useRef<string | null>(null);
  const abortController = useRef<AbortController | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const query = input.trim();
    if (!query || isSending) {
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

    try {
      const response = await fetch("/api/agent/query", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({
          query,
          conversation_id: conversationId.current,
        }),
        signal: controller.signal,
      });

      if (response.status === 401) {
        router.push("/login");
        return;
      }

      if (!response.ok || !response.body) {
        const responseBody = (await response.json().catch(() => null)) as {
          detail?: string;
        } | null;
        setError(responseBody?.detail ?? `Request failed (${response.status}).`);
        return;
      }

      let finalAnswer: string | null = null;
      let sawError = false;
      for await (const streamEvent of parseSSEStream(response.body)) {
        setGraph((current) => (current ? applyStreamEvent(current, streamEvent) : current));

        switch (streamEvent.type) {
          case "token":
            if (streamEvent.node === "decision") {
              setStreamingText((current) => current + streamEvent.text);
            }
            break;
          case "citation_check":
            if (!streamEvent.passed) {
              // Per run_execution_streaming()'s own docstring: more
              // token events after a failed check are a FRESH draft,
              // not a continuation -- discard what streamed so far.
              setStreamingText("");
            }
            break;
          case "error":
            sawError = true;
            setError(streamEvent.detail);
            break;
          case "done":
            finalAnswer = streamEvent.answer;
            conversationId.current = streamEvent.conversation_id;
            break;
          default:
            break;
        }
      }

      if (!sawError) {
        setMessages((current) => [
          ...current,
          { role: "assistant", content: finalAnswer ?? "No answer was produced for this query." },
        ]);
      }
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        setError("Could not reach the server.");
      }
    } finally {
      setStreamingText("");
      setIsSending(false);
      abortController.current = null;
    }
  }

  function handleStop(): void {
    abortController.current?.abort();
  }

  async function handleLogout(): Promise<void> {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="flex flex-1 flex-col bg-(--color-canvas)">
      <header className="flex items-center justify-between border-b border-(--color-hairline) bg-(--color-surface) px-6 py-3">
        <div className="flex items-baseline gap-3">
          <h1 className="text-[16px] font-medium text-(--color-text-hi)">RetailOps AI</h1>
          <span className="font-mono text-[11px] text-(--color-text-mid)" data-numeric>
            Online Retail II · as-of 2011-12-09
          </span>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          className="rounded-[6px] px-2 py-1 text-[13px] text-(--color-text-mid) transition-colors duration-150 hover:text-(--color-text-hi) focus-visible:outline focus-visible:outline-2 focus-visible:outline-(--color-accent)"
        >
          Log out
        </button>
      </header>

      <div className="flex flex-1 flex-col overflow-hidden lg:flex-row">
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-6 py-6">
            {messages.length === 0 && !isSending && (
              <p className="max-w-[68ch] text-[14px] leading-[1.6] text-(--color-text-mid)">
                Ask about inventory, forecasts, or performance — e.g. &ldquo;What should I reorder
                today?&rdquo;
              </p>
            )}
            {messages.map((message, index) => (
              <div
                key={index}
                className={`max-w-[85%] rounded-[6px] px-4 py-2 text-[14px] leading-[1.6] whitespace-pre-wrap ${
                  message.role === "user"
                    ? "self-end bg-(--color-accent-dim) text-(--color-text-hi)"
                    : "self-start border border-(--color-hairline) bg-(--color-surface) text-(--color-text-hi)"
                }`}
              >
                {message.content}
              </div>
            ))}

            {isSending && (
              <div className="self-start rounded-[6px] border border-(--color-hairline) bg-(--color-surface) px-4 py-2 text-[14px] leading-[1.6] whitespace-pre-wrap text-(--color-text-hi)">
                {streamingText || "Thinking…"}
              </div>
            )}

            {error && (
              <p role="alert" className="self-start text-[14px] text-(--color-danger)">
                {error}
              </p>
            )}
          </div>

          <form onSubmit={handleSubmit} className="flex items-end gap-2 px-6 pb-6">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              rows={1}
              placeholder="Ask a question…"
              className="flex-1 resize-none rounded-[6px] border border-(--color-hairline) bg-(--color-surface) px-3 py-2 text-[14px] text-(--color-text-hi) outline-none placeholder:text-(--color-text-low) focus-visible:border-(--color-accent) focus-visible:outline focus-visible:outline-2 focus-visible:outline-(--color-accent)"
            />
            {isSending ? (
              <button
                type="button"
                onClick={handleStop}
                className="rounded-[6px] border border-(--color-hairline) px-4 py-2 text-[13px] font-medium text-(--color-text-hi) transition-colors duration-150 hover:border-(--color-hairline-hi) focus-visible:outline focus-visible:outline-2 focus-visible:outline-(--color-accent)"
              >
                Stop
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className="rounded-[6px] bg-(--color-accent) px-4 py-2 text-[13px] font-medium text-(--color-canvas) transition-colors duration-150 hover:opacity-90 disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-(--color-accent)"
              >
                Send
              </button>
            )}
          </form>
        </div>

        <aside className="flex h-[320px] shrink-0 flex-col border-t border-(--color-hairline) bg-(--color-canvas) lg:h-auto lg:w-[420px] lg:border-t-0 lg:border-l">
          <div className="flex items-center justify-between px-4 py-3">
            <h2 className="text-[13px] font-medium text-(--color-text-mid) uppercase tracking-[0.04em]">
              Execution graph
            </h2>
          </div>
          {graph?.replanNote && (
            <p className="mx-4 mb-3 rounded-[6px] bg-(--color-accent-dim) px-3 py-2 text-[13px] leading-[1.45] text-(--color-text-hi)">
              {graph.replanNote}
            </p>
          )}
          {graph?.citationNote && (
            <p className="mx-4 mb-3 text-[12px] text-(--color-text-mid) italic">
              {graph.citationNote}
            </p>
          )}
          <div className="min-h-0 flex-1 px-4 pb-4">
            {graph ? (
              <ExecutionGraph graph={graph} />
            ) : (
              <div className="flex h-full items-center justify-center rounded-[6px] border border-(--color-hairline) px-4 text-center text-[13px] text-(--color-text-mid)">
                The live agent graph for your next question will appear here as it runs.
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
