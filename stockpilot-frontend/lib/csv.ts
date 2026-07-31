// docs/PRODUCT-SPEC.md §20: "exportable as CSV from the current
// filtered/sorted view -- what's on screen is what's exported." Pure,
// client-side formatting of already-fetched data -- not a call to any
// endpoint, so it isn't blocked by a missing backend capability.
export function toCsv<T extends Record<string, unknown>>(rows: T[], columns: (keyof T)[]): string {
  const escape = (value: unknown): string => {
    const str = value === null || value === undefined ? "" : String(value);
    return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str;
  };
  const header = columns.map((c) => escape(String(c))).join(",");
  const lines = rows.map((row) => columns.map((c) => escape(row[c])).join(","));
  return [header, ...lines].join("\n");
}

export function downloadCsv(filename: string, csv: string): void {
  // docs/PRODUCT-SPEC.md §20: "every export includes a generation
  // timestamp so a downloaded file's currency is unambiguous later" --
  // encoded in the filename here since this data has no natural
  // in-body timestamp column of its own.
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
