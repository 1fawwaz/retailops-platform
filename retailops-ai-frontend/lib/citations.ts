import type { CitationEntry } from "@/lib/types";

/**
 * Mirrors orchestration/validator.py::NUMBER_PATTERN and _normalize()
 * EXACTLY -- the frontend needs to find the SAME token boundaries and
 * the SAME normalized values the backend used to build the `citations`
 * list, so every occurrence in the rendered text (not just the first,
 * which is all the deduped `citations` list itself carries) can be
 * matched back to its resolution.
 */
const NUMBER_PATTERN = /-?[$£€]?\d[\d,]*(?:\.\d+)?%?/g;

export function normalizeToken(token: string): number | null {
  const cleaned = token.replace(/[$£€,%]/g, "");
  const value = Number.parseFloat(cleaned);
  if (Number.isNaN(value)) {
    return null;
  }
  return Math.round(value * 100) / 100;
}

export type TextSegment =
  | { type: "text"; value: string }
  | { type: "citation"; token: string; citation: CitationEntry };

/** Splits `text` into plain-text and citation segments for rendering,
 * using the citations list orchestration/validator.py::resolve_citations()
 * already computed server-side -- this function does no grounding logic
 * of its own, purely re-finds where each already-resolved value occurs
 * in the original text so it can be wrapped in a chip there.
 */
export function buildCitationSegments(text: string, citations: CitationEntry[]): TextSegment[] {
  if (citations.length === 0) {
    return [{ type: "text", value: text }];
  }

  const byValue = new Map<number, CitationEntry>();
  for (const citation of citations) {
    byValue.set(citation.value, citation);
  }

  const segments: TextSegment[] = [];
  let lastIndex = 0;
  for (const match of text.matchAll(NUMBER_PATTERN)) {
    const raw = match[0];
    const index = match.index;
    const normalized = normalizeToken(raw);
    const citation = normalized === null ? undefined : byValue.get(normalized);
    if (!citation) {
      // A numeric-looking substring the backend's own extraction also
      // saw but couldn't normalize, or (defensively) one this citation
      // list doesn't cover -- render as plain text rather than guess.
      continue;
    }
    if (index > lastIndex) {
      segments.push({ type: "text", value: text.slice(lastIndex, index) });
    }
    segments.push({ type: "citation", token: raw, citation });
    lastIndex = index + raw.length;
  }
  if (lastIndex < text.length) {
    segments.push({ type: "text", value: text.slice(lastIndex) });
  }
  return segments;
}
