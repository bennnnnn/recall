/**
 * A flush of a streaming reply costs the text that arrived, not the reply so
 * far: the characters handed to `preprocessMarkdown` and to the markdown
 * parser in a flush stay level as the reply grows. Counted, never timed.
 */
import { act, render } from "@testing-library/react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { STREAMING_REPLIES } from "@/lib/__tests__/fixtures/streamingReplies";
import * as preprocess from "@/lib/markdown/preprocess";
import { formatAssistantMathExpr } from "@/lib/math/formatInput";

const mockWork = { preprocessed: 0, parsed: 0 };

jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: "LinkPreviewCard" }));
jest.mock("react-native-markdown-display", () => {
  const actual = jest.requireActual("react-native-markdown-display");
  const Markdown = actual.default;
  return {
    ...actual,
    __esModule: true,
    default: (props: { children: string }) => {
      mockWork.parsed += props.children.length;
      return <Markdown {...props} />;
    },
  };
});

const realPreprocess = preprocess.preprocessMarkdown;
jest.spyOn(preprocess, "preprocessMarkdown").mockImplementation((text, ...rest) => {
  mockWork.preprocessed += text.length;
  return realPreprocess(text, ...rest);
});

/** The fixture replies one after another: a reply several times the usual length. */
const LONG_REPLY = [
  STREAMING_REPLIES.maths,
  STREAMING_REPLIES.tips,
  STREAMING_REPLIES.mixed,
  STREAMING_REPLIES.maths,
  STREAMING_REPLIES.nested,
  STREAMING_REPLIES.maths,
].join("\n\n");

type Flush = { at: number; preprocessed: number; parsed: number };

async function streamCounting(text: string, step = 24): Promise<Flush[]> {
  const view = await render(
    <MarkdownContent content="" streaming mathFormat={formatAssistantMathExpr} />,
  );
  const flushes: Flush[] = [];
  for (let end = step; end < text.length + step; end += step) {
    const at = Math.min(end, text.length);
    mockWork.preprocessed = 0;
    mockWork.parsed = 0;
    await act(async () => {
      view.rerender(
        <MarkdownContent content={text.slice(0, at)} streaming mathFormat={formatAssistantMathExpr} />,
      );
    });
    flushes.push({ at, ...mockWork });
  }
  await view.unmount();
  return flushes;
}

function mean(values: number[]): number {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

describe("a streaming reply's work per flush", () => {
  it("stays level from the start of a long reply to its end", async () => {
    const flushes = await streamCounting(LONG_REPLY);
    expect(LONG_REPLY.length).toBeGreaterThan(10_000);
    const early = flushes.filter((flush) => flush.at > 1_000 && flush.at <= 4_000);
    const late = flushes.filter((flush) => flush.at > LONG_REPLY.length - 3_000);

    for (const kind of ["preprocessed", "parsed"] as const) {
      // Late in the reply a flush does about what it did early on…
      expect(mean(late.map((flush) => flush[kind]))).toBeLessThan(
        2 * mean(early.map((flush) => flush[kind])) + 200,
      );
      // …and no flush comes near the reply's whole length.
      expect(Math.max(...late.map((flush) => flush[kind]))).toBeLessThan(LONG_REPLY.length / 4);
    }
  }, 300_000);
});
