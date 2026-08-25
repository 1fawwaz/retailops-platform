import type { CitationEntry } from "./types";

const NUMBER_PATTERN = /-?[$£€₹]?\d[\d,]*(?:\.\d+)?%?/g;

export function normalizeToken(token: string): number | null {
  const cleaned = token.replace(/[₹$£€,%]/g, "");
  const value = Number.parseFloat(cleaned);
  if (Number.isNaN(value)) {
    return null;
  }
  return Math.round(value * 100) / 100;
}

export type TextSegment =
  | { type: "text"; value: string }
  | { type: "citation"; token: string; citation: CitationEntry };

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
