import type { AgentStreamEvent } from "./types";

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
    return JSON.parse(dataLine) as AgentStreamEvent;
  } catch {
    return null;
  }
}
