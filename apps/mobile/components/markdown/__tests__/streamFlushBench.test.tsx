/**
 * Flush benchmark: 20k-character replies streamed through the row's real
 * pipeline (support/streamBench.ts) in 30-character flushes, as a reply
 * streams at ~30 flushes a second. Prints the time, the preprocess calls and
 * the characters they read. Off by default: `STREAM_BENCH=1 pnpm jest
 * streamFlushBench`. The counts are deterministic; the times are this machine's.
 */
import { cleanup, render } from "@testing-library/react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { streamReply } from "@/lib/__tests__/support/streamBench";
import { BENCH_REPLIES } from "@/lib/__tests__/fixtures/benchReplies";

jest.mock("expo-file-system/legacy", () => ({ cacheDirectory: "file:///cache/" }));
jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: () => null }));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));

const mockCalls = { preprocess: 0, preprocessChars: 0 };

jest.mock("@/lib/markdown/preprocess", () => {
  const actual = jest.requireActual<typeof import("@/lib/markdown/preprocess")>(
    "@/lib/markdown/preprocess",
  );
  return {
    ...actual,
    preprocessMarkdown: (...args: Parameters<typeof actual.preprocessMarkdown>) => {
      mockCalls.preprocess += 1;
      mockCalls.preprocessChars += args[0].length;
      return actual.preprocessMarkdown(...args);
    },
  };
});

const bench = process.env.STREAM_BENCH ? describe : describe.skip;

bench("streaming flush benchmark (20k chars, 30-char flushes)", () => {
  it.each(Object.keys(BENCH_REPLIES))("%s", (name) => {
    const reply = BENCH_REPLIES[name as keyof typeof BENCH_REPLIES];
    streamReply(reply.slice(0, 2000));
    mockCalls.preprocess = 0;
    mockCalls.preprocessChars = 0;
    const { stats } = streamReply(reply);
    console.log(
      JSON.stringify({
        name,
        chars: reply.length,
        flushes: stats.flushes,
        ms: Math.round(stats.ms),
        rowMs: Math.round(stats.rowMs),
        parseMs: Math.round(stats.parseMs),
        preprocessCalls: mockCalls.preprocess,
        preprocessChars: mockCalls.preprocessChars,
        unstableChars: stats.unstableChars,
        parsedChars: stats.parsedChars,
        chunks: stats.chunks,
        chunkDrops: stats.chunkDrops,
      }),
    );
  });
});

/** A long checklist with nested items: each item asks about its whole list (MX-6). */
const CHECKLIST = Array.from(
  { length: 600 },
  (_, i) => `- [${i % 3 ? "x" : " "}] Task ${i + 1} with a short note\n  - [x] its first step\n  - [ ] its second step`,
).join("\n");

bench("drawing a 600-item nested checklist", () => {
  it("renders it settled five times", async () => {
    await render(<MarkdownContent content={CHECKLIST} />);
    cleanup();
    const started = performance.now();
    for (let i = 0; i < 5; i += 1) {
      await render(<MarkdownContent content={`${CHECKLIST}\n\nRound ${i}.`} />);
      cleanup();
    }
    console.log(JSON.stringify({ name: "checklist", ms: Math.round(performance.now() - started) }));
  });
});
