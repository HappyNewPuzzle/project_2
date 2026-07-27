import { describe, expect, it } from "vitest";
import {
  consumeSseStream,
  extractSseBlocks,
  parseSseBlock,
} from "./sse";

describe("parseSseBlock", () => {
  it("event와 여러 data 줄을 JSON으로 읽는다", () => {
    const event = parseSseBlock(
      'event: token\ndata: {"delta":\ndata: "안녕"}',
    );

    expect(event).toEqual({ event: "token", data: { delta: "안녕" } });
  });

  it("event가 없으면 message를 기본값으로 사용한다", () => {
    expect(parseSseBlock('data: {"ok":true}')).toEqual({
      event: "message",
      data: { ok: true },
    });
  });
});

describe("extractSseBlocks", () => {
  it("CRLF를 정규화하고 미완성 꼬리를 남긴다", () => {
    expect(
      extractSseBlocks('event: token\r\ndata: {"delta":"A"}\r\n\r\nevent:'),
    ).toEqual({
      blocks: ['event: token\ndata: {"delta":"A"}'],
      remainder: "event:",
    });
  });
});

describe("consumeSseStream", () => {
  it("조각난 chunk와 마지막 구분자 없는 이벤트도 소비한다", async () => {
    const encoder = new TextEncoder();
    const chunks = [
      'event: token\ndata: {"del',
      'ta":"A"}\n\nevent: done\ndata: {}',
    ];
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(chunk));
        }
        controller.close();
      },
    });
    const received: string[] = [];

    await consumeSseStream(stream, (event) => {
      received.push(event.event);
    });

    expect(received).toEqual(["token", "done"]);
  });
});
