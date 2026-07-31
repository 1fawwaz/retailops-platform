// docs/DESIGN-SPEC.md §6: "one sentence saying what will appear here and
// one action. Not an illustration. Not 'No data.'" docs/PRODUCT-SPEC.md
// §18 distinguishes a genuinely-empty resource from a zero-match filtered
// view -- this component is for the former; a resource page wires its
// own filtered-empty copy once it has real filters (Stage 2+).
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-2 text-center">
      <h2 className="text-[16px] font-medium text-[var(--color-text-hi)]">{title}</h2>
      <p className="max-w-[40ch] text-[13px] text-[var(--color-text-mid)]">{description}</p>
      {action}
    </div>
  );
}
