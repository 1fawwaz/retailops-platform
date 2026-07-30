"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { AgentQueryResponse, ChatMessage } from "@/lib/types";

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
    setIsSending(true);

    try {
      const response = await fetch("/api/agent/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          conversation_id: conversationId.current,
        }),
      });

      if (response.status === 401) {
        router.push("/login");
        return;
      }

      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { detail?: string } | null;
        setError(body?.detail ?? `Request failed (${response.status}).`);
        return;
      }

      const data = (await response.json()) as AgentQueryResponse;
      conversationId.current = data.conversation_id;
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: data.answer ?? "No answer was produced for this query.",
        },
      ]);
    } catch {
      setError("Could not reach the server.");
    } finally {
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
        {messages.length === 0 && (
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
          <div className="self-start rounded-lg bg-white px-4 py-2 text-sm text-zinc-500 shadow-sm dark:bg-zinc-900 dark:text-zinc-400">
            Thinking…
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
