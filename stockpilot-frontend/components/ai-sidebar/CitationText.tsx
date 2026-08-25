"use client";

import { buildCitationSegments } from "../../lib/citations";
import type { CitationEntry } from "../../lib/types";

export function CitationText({
  text,
  citations,
  onOpenCitation,
}: {
  text: string;
  citations: CitationEntry[];
  onOpenCitation: (citation: CitationEntry) => void;
}) {
  const segments = buildCitationSegments(text, citations);

  return (
    <span className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--color-text-high)]">
      {segments.map((segment, index) => {
        if (segment.type === "text") {
          return <span key={index}>{segment.value}</span>;
        }

        const { citation, token } = segment;
        if (citation.tool_call_id === null) {
          return (
            <span key={index} className="inline-flex items-baseline gap-1 mx-0.5">
              <span className="font-mono text-[var(--color-danger)] font-medium" data-numeric>
                {token}
              </span>
              <span className="rounded bg-[var(--color-danger)] px-1 py-0.5 text-[9px] font-semibold tracking-wider text-[var(--color-canvas)] uppercase">
                Missing source
              </span>
            </span>
          );
        }

        return (
          <button
            key={index}
            type="button"
            onClick={() => onOpenCitation(citation)}
            className="mx-0.5 rounded px-0.5 font-mono text-[var(--color-text-high)] underline decoration-[var(--color-border-hover)] decoration-dotted underline-offset-2 transition-colors duration-150 hover:bg-[var(--color-canvas)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            data-numeric
          >
            {token}
            <sup className="ml-px text-[10px] text-[var(--color-text-mid)] font-semibold">†</sup>
          </button>
        );
      })}
    </span>
  );
}
