import { RouteGuard } from "../../lib/auth/RouteGuard";
import { QueryProvider } from "../../lib/query/provider";
import { AppShell } from "../../components/layout/AppShell";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <RouteGuard>
      <QueryProvider>
        <AppShell>{children}</AppShell>
      </QueryProvider>
    </RouteGuard>
  );
}
