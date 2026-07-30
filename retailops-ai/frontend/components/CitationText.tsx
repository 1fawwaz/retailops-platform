"use client";

import { buildCitationSegments } from "@/lib/citations";
import type { CitationEntry } from "@/lib/types";

/**
 * docs/DESIGN-SPEC.md §5 "Citation chip": every figure produced by a
 * tool call renders as a chip -- the value in mono, followed by a 10px
 * superscript reference marker; hover raises the background to
 * --color-raised; click opens the provenance drawer. A figure with no
 * resolvable tool call renders with a MISSING SOURCE label in
 * --color-danger, never silently as normal text.
 */
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
    <span className="whitespace-pre-wrap">
      {segments.map((segment, index) => {
        if (segment.type === "text") {
          return <span key={index}>{segment.value}</span>;
        }

        const { citation, token } = segment;
        if (citation.tool_call_id === null) {
          return (
            <span key={index} className="inline-flex items-baseline gap-1">
              <span className="font-mono text-(--color-danger)" data-numeric>
                {token}
              </span>
              <span className="rounded-[6px] bg-(--color-danger) px-1 py-0.5 text-[10px] font-medium tracking-[0.04em] text-(--color-canvas) uppercase">
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
            className="rounded-[3px] font-mono text-(--color-text-hi) underline decoration-(--color-hairline-hi) decoration-dotted underline-offset-2 transition-colors duration-150 hover:bg-(--color-raised) focus-visible:outline focus-visible:outline-2 focus-visible:outline-(--color-accent)"
            data-numeric
          >
            {token}
            <sup className="ml-px text-[10px] text-(--color-text-mid)">†</sup>
          </button>
        );
      })}
    </span>
  );
}
