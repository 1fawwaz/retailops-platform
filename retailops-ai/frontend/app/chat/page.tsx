"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { parseSSEStream } from "@/lib/sse";
import type { ChatMessage } from "@/lib/types";

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamingText, setStreamingText] = useState("");
  const [completedAgents, setCompletedAgents] = useState<string[]>([]);
  const [progressNote, setProgressNote] = useState<string | null>(null);
  const conversationId = useRef<string | null>(null);

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
    setCompletedAgents([]);
    setProgressNote(null);
    setIsSending(true);

    try {
      const response = await fetch("/api/agent/query", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({
          query,
          conversation_id: conversationId.current,
        }),
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
        switch (streamEvent.type) {
          case "token":
            if (streamEvent.node === "decision") {
              setStreamingText((current) => current + streamEvent.text);
            }
            break;
          case "agent_completed":
            setCompletedAgents((current) =>
              current.includes(streamEvent.agent) ? current : [...current, streamEvent.agent],
            );
            break;
          case "replan_judgement":
            setProgressNote(
              streamEvent.sufficient
                ? null
                : `Gathering more evidence: ${streamEvent.next_action}`,
            );
            if (!streamEvent.sufficient) {
              // A new retrieval round is starting -- the agents it
              // retries will emit fresh agent_completed events, so drop
              // them from the "done" pill list rather than show a stale
              // checkmark for evidence that's being redone.
              setCompletedAgents((current) =>
                current.filter((agent) => !streamEvent.agents_to_retry.includes(agent)),
              );
            }
            break;
          case "citation_check":
            if (streamEvent.passed) {
              setProgressNote(null);
            } else {
              // Per run_execution_streaming()'s own docstring: more
              // token events after a failed check are a FRESH draft,
              // not a continuation -- discard what streamed so far.
              setStreamingText("");
              setProgressNote("A citation check failed; regenerating the answer…");
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
    } catch {
      setError("Could not reach the server.");
    } finally {
      setStreamingText("");
      setCompletedAgents([]);
      setProgressNote(null);
      setIsSending(false);
    }
  }

  async function handleLogout(): Promise<void> {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="flex flex-1 flex-col bg-zinc-50 dark:bg-black">
      <header className="flex items-center justify-between border-b border-zinc-200 bg-white px-6 py-3 dark:border-zinc-800 dark:bg-zinc-950">
        <h1 className="text-sm font-semibold text-zinc-950 dark:text-zinc-50">RetailOps AI</h1>
        <button
          type="button"
          onClick={handleLogout}
          className="text-sm text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-50"
        >
          Log out
        </button>
      </header>

      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 overflow-y-auto px-6 py-6">
        {messages.length === 0 && !isSending && (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Ask about inventory, forecasts, or performance — e.g. &ldquo;What should I reorder
            today?&rdquo;
          </p>
        )}
        {messages.map((message, index) => (
          <div
            key={index}
            className={`max-w-[85%] rounded-lg px-4 py-2 text-sm whitespace-pre-wrap ${
              message.role === "user"
                ? "self-end bg-zinc-950 text-white dark:bg-zinc-50 dark:text-zinc-950"
                : "self-start bg-white text-zinc-950 shadow-sm dark:bg-zinc-900 dark:text-zinc-50"
            }`}
          >
            {message.content}
          </div>
        ))}

        {isSending && (
          <div className="flex max-w-[85%] flex-col gap-2 self-start">
            {completedAgents.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {completedAgents.map((agent) => (
                  <span
                    key={agent}
                    className="rounded-full bg-zinc-200 px-2 py-0.5 text-xs text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                  >
                    {agent} ✓
                  </span>
                ))}
              </div>
            )}
            {progressNote && (
              <p className="text-xs text-zinc-500 italic dark:text-zinc-400">{progressNote}</p>
            )}
            <div className="rounded-lg bg-white px-4 py-2 text-sm whitespace-pre-wrap text-zinc-950 shadow-sm dark:bg-zinc-900 dark:text-zinc-50">
              {streamingText || "Thinking…"}
            </div>
          </div>
        )}

        {error && (
          <p role="alert" className="self-start text-sm text-red-600 dark:text-red-400">
            {error}
          </p>
        )}
      </div>

      <form
        onSubmit={handleSubmit}
        className="mx-auto flex w-full max-w-3xl items-end gap-2 px-6 pb-6"
      >
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
          className="flex-1 resize-none rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-950 outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
        />
        <button
          type="submit"
          disabled={isSending || !input.trim()}
          className="rounded-md bg-zinc-950 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-800 disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-950 dark:hover:bg-zinc-200"
        >
          Send
        </button>
      </form>
    </div>
  );
}
