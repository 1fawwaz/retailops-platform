import { Suspense } from "react";
import { LoginForm } from "./LoginForm";

// useSearchParams() (read inside LoginForm, for the post-login `redirect`
// param) requires a Suspense boundary around itself in the App Router --
// this Server Component page.tsx exists only to provide it.
export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-canvas)]">
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
    </div>
  );
}
