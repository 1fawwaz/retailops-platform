// docs/ARCHITECTURE.md § AI Integration Architecture: the real sidebar
// (context-aware queries, SSE streaming, citation chips, provenance
// drawer) is Stage 10 -- see BUILD.md Stage 10 and its component-reuse
// ADR requirement, not yet decided. This is only the mount point Stage 0
// asks for: reserves the layout slot so Stage 10 doesn't need a shell
// re-layout, renders nothing that claims to be the real feature.
export function AiSidebarMount() {
  return null;
}
