import type { AgentStreamEvent } from "@/lib/types";

/**
 * Parses the exact wire format api/agent.py::_sse_event() produces:
 * `event: <type>\ndata: <json>\n\n`. Not the browser's native
 * EventSource -- that API only supports GET requests with no custom
 * headers/body, and this endpoint needs a POST carrying the query
 * plus an Authorization header attached server-side (see
 * app/api/agent/query/route.ts). Reading the fetch Response's own
 * ReadableStream by hand is the standard workaround for POST-based SSE.
 */
export async function* parseSSEStream(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<AgentStreamEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const rawEvent = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const event = parseEventBlock(rawEvent);
        if (event) {
          yield event;
        }
        boundary = buffer.indexOf("\n\n");
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function parseEventBlock(block: string): AgentStreamEvent | null {
  let dataLine: string | null = null;
  for (const line of block.split("\n")) {
    if (line.startsWith("data: ")) {
      dataLine = line.slice("data: ".length);
    }
  }
  if (dataLine === null) {
    return null;
  }
  try {
    // The "type" field is already inside the JSON payload itself
    // (api/agent.py's _sse_event() puts it in `data`, not only in the
    // `event:` line), so parsing `data` alone is sufficient and avoids
    // maintaining the discriminant in two places.
    return JSON.parse(dataLine) as AgentStreamEvent;
  } catch {
    return null;
  }
}
