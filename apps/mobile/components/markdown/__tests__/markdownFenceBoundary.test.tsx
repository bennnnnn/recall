// One rich block that throws while it renders degrades on its own: the prose
// and the other blocks of the reply still draw, and the crash is reported once.
import { render } from "@testing-library/react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { MarkdownErrorBoundary } from "@/components/MarkdownErrorBoundary";
import { reportBoundaryError } from "@/lib/sentry";

jest.mock("@/lib/sentry", () => ({ reportBoundaryError: jest.fn() }));
jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: "LinkPreviewCard" }));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  writeAsStringAsync: jest.fn(),
  EncodingType: { UTF8: "utf8" },
}));
jest.mock("@/components/rich/MathView", () => {
  const { Text: RNText } = jest.requireActual("react-native");
  return { MathBlock: ({ latex }: { latex: string }) => <RNText>{`MATH:${latex}`}</RNText> };
});
jest.mock("@/components/rich/QuizCard", () => ({
  QuizCard: () => {
    throw new Error("quiz render failed");
  },
}));
jest.mock("@/components/rich/LazyHeavyRich", () => ({
  ...jest.requireActual("@/components/rich/LazyHeavyRich"),
  LazyFunctionGraphBlock: () => {
    throw new Error("graph render failed");
  },
}));
jest.mock("@/components/CodeBlock", () => {
  const { Text: RNText } = jest.requireActual("react-native");
  return {
    CodeBlock: ({ code, lang }: { code: string; lang: string }) => (
      <RNText>{`CODE(${lang}):${code}`}</RNText>
    ),
  };
});

const QUIZ = '{"question":"Pick one","options":["a","b"],"answer":0}';
const REPLY = [
  "Here is the intro.",
  "",
  "```quiz",
  QUIZ,
  "```",
  "",
  "```math",
  "x^2 + 1",
  "```",
  "",
  "And the closing line.",
].join("\n");

/** As a chat bubble draws a reply: the whole-reply boundary is the last resort. */
function Reply() {
  return (
    <MarkdownErrorBoundary resetKey="m1" content={REPLY}>
      <MarkdownContent content={REPLY} />
    </MarkdownErrorBoundary>
  );
}

describe("a rich block that throws while it renders", () => {
  const warn = jest.spyOn(console, "warn").mockImplementation(() => undefined);
  const error = jest.spyOn(console, "error").mockImplementation(() => undefined);

  beforeEach(() => jest.clearAllMocks());
  afterAll(() => {
    warn.mockRestore();
    error.mockRestore();
  });

  it("falls back on its own while the text and the other blocks render", async () => {
    const screen = await render(<Reply />);

    expect(screen.getByText("Here is the intro.")).toBeTruthy();
    expect(screen.getByText("MATH:x^2 + 1")).toBeTruthy();
    expect(screen.getByText("And the closing line.")).toBeTruthy();
    // The broken block: a short note, then what the reply's crash fallback
    // draws for it (FallbackMarkdown): here its source as plain code.
    expect(screen.getByText("rich.block_render_failed")).toBeTruthy();
    expect(screen.getByText(QUIZ)).toBeTruthy();
  });

  it("reports the crash once, tagged as a fence", async () => {
    const screen = await render(<Reply />);
    await screen.rerender(<Reply />);

    expect(reportBoundaryError).toHaveBeenCalledTimes(1);
    expect(reportBoundaryError).toHaveBeenCalledWith(
      "fence",
      expect.objectContaining({ message: "quiz render failed" }),
      expect.any(String),
    );
  });

  it("names a diagram that failed instead of drawing it again", async () => {
    const graph = '{"functions":[{"expr":"x^2"}]}';
    const reply = `Intro.\n\n\`\`\`graph\n${graph}\n\`\`\`\n\n\`\`\`math\ny = 2\n\`\`\``;
    const screen = await render(
      <MarkdownErrorBoundary resetKey="m2" content={reply}>
        <MarkdownContent content={reply} />
      </MarkdownErrorBoundary>,
    );

    expect(screen.getByText("Intro.")).toBeTruthy();
    expect(screen.getByText("MATH:y = 2")).toBeTruthy();
    expect(screen.getByText("rich.block_render_failed")).toBeTruthy();
    expect(screen.getByText("rich.diagram")).toBeTruthy();
    expect(screen.queryByText(graph)).toBeNull();
    expect(reportBoundaryError).toHaveBeenCalledTimes(1);
  });
});
