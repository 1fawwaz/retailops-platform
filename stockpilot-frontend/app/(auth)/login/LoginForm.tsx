"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { login } from "../../../lib/auth/session";
import { useSession } from "../../../lib/auth/useSession";
import { AppError } from "../../../lib/api/errors";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const session = useSession();

  useEffect(() => {
    if (session !== null) {
      router.replace("/dashboard");
    }
  }, [session, router]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
      const redirect = searchParams.get("redirect");
      router.replace(redirect && redirect.startsWith("/") ? redirect : "/dashboard");
    } catch (err) {
      if (err instanceof AppError) {
        setError(
          err.kind === "auth" || err.kind === "business-rule"
            ? "Incorrect email or password."
            : err.message,
        );
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="w-full max-w-sm rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-8">
      <h1 className="mb-1 text-[20px] text-[var(--color-text-hi)]">StockPilot</h1>
      <p className="mb-6 text-[13px] text-[var(--color-text-mid)]">Sign in to continue.</p>
      <form onSubmit={handleSubmit} noValidate>
        <div className="mb-4">
          <label htmlFor="email" className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
            Email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            required
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? "login-error" : undefined}
            className="w-full rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-2 text-[14px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          />
        </div>
        <div className="mb-4">
          <label htmlFor="password" className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? "login-error" : undefined}
            className="w-full rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-2 text-[14px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          />
        </div>
        {error && (
          <p id="login-error" role="alert" className="mb-4 text-[13px] text-[var(--color-danger)]">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-[6px] bg-[var(--color-accent)] px-3 py-2 text-[14px] font-medium text-[var(--color-canvas)] transition-colors duration-150 disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)]"
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
