import type { SseEvent } from "../types/api";

// CRLF와 LF를 같은 방식으로 처리해 운영 프록시가 줄바꿈을 바꿔도 파싱합니다.
function normalizeLineEndings(value: string): string {
  return value.replace(/\r\n/g, "\n");
}

// 완성된 SSE 블록 한 개에서 event와 여러 data 줄을 읽습니다.
export function parseSseBlock(block: string): SseEvent | null {
  let event = "message";
  const dataLines: string[] = [];

  for (const line of normalizeLineEndings(block).split("\n")) {
    if (!line || line.startsWith(":")) {
      continue;
    }
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trimStart();
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  if (dataLines.length === 0) {
    return null;
  }

  const rawData = dataLines.join("\n");
  return {
    event,
    data: rawData ? JSON.parse(rawData) : {},
  };
}

// 네트워크 chunk 경계와 SSE 이벤트 경계가 달라도 완성된 블록만 분리합니다.
export function extractSseBlocks(
  buffer: string,
): { blocks: string[]; remainder: string } {
  const normalized = normalizeLineEndings(buffer);
  const parts = normalized.split("\n\n");
  return {
    blocks: parts.slice(0, -1),
    remainder: parts.at(-1) ?? "",
  };
}

// fetch ReadableStream을 끝까지 읽으며 파싱된 SSE 이벤트를 순서대로 전달합니다.
export async function consumeSseStream(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: SseEvent) => void | Promise<void>,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const { blocks, remainder } = extractSseBlocks(buffer);
      buffer = remainder;

      for (const block of blocks) {
        const event = parseSseBlock(block);
        if (event) {
          await onEvent(event);
        }
      }

      if (done) {
        break;
      }
    }

    // 서버가 마지막 빈 줄 없이 연결을 닫아도 남은 이벤트를 한 번 처리합니다.
    if (buffer.trim()) {
      const event = parseSseBlock(buffer);
      if (event) {
        await onEvent(event);
      }
    }
  } finally {
    reader.releaseLock();
  }
}
