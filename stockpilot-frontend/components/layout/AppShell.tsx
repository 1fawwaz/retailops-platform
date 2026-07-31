import { Header } from "./Header";
import { LeftNav } from "./LeftNav";
import { Breadcrumb } from "./Breadcrumb";
import { AiSidebarMount } from "../ai-sidebar/AiSidebarMount";

// BUILD.md Stage 0: "App shell: top nav, left nav (route list per §3 of
// CLAUDE.md), header with user menu, breadcrumb slot, AI sidebar mount
// point (empty until Stage 10)." A Server Component -- none of the
// interactivity lives here, only composition of the Client Component
// pieces that need it (Header, LeftNav, Breadcrumb).
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full min-h-screen flex-col bg-[var(--color-canvas)]">
      <Header />
      <div className="flex flex-1">
        <LeftNav />
        <div className="flex flex-1 flex-col">
          <Breadcrumb />
          <main className="flex-1 px-4 pb-8">{children}</main>
        </div>
      </div>
      <AiSidebarMount />
    </div>
  );
}
