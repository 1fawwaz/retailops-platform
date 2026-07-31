import { EmptyState } from "../../../../components/ui/EmptyState";

// docs/PRODUCT-SPEC.md §24 Settings / BUILD.md Stage 9.
export default function ApiKeysSettingsPage() {
  return (
    <EmptyState
      title="API Keys"
      description="API key management will appear here once Stage 9 wires it against StockPilot Core."
    />
  );
}
