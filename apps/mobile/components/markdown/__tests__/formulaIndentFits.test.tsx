// The owner's S23 (2026-11-11): "n! = n × (n−1) × (n−2) × ⋯ × 1", a working line under its
// heading, ran past the phone's right edge and scrolled, with the working column's indent
// empty on its left. A formula now takes that room before it scrolls; one that fits keeps
// the indent, and one wider than the whole line still scrolls.
import { render } from "@testing-library/react-native";
import { Dimensions } from "react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { WORK_INDENT } from "@/components/markdown/markdownContentStyles";
import { fittedIndent } from "@/lib/math/layout";

jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: "LinkPreviewCard" }));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  writeAsStringAsync: jest.fn(),
  EncodingType: { UTF8: "utf8" },
}));
jest.mock("@/components/WebPreviewCodeBlock", () => ({ WebPreviewCodeBlock: "WebPreviewCodeBlock" }));
jest.mock("@/components/rich/CircularClockBlock", () => ({ CircularClockBlock: "CircularClockBlock" }));
jest.mock("@/components/rich/AnswerBlock", () => ({ AnswerBlock: "AnswerBlock" }));

const FACTORIAL = String.raw`$n! = n \times (n-1) \times (n-2) \times \cdots \times 1$`;
const SHORT = "$x = 2$";
// Wider than the whole line of a 360-point phone: it still scrolls.
const VERY_LONG = String.raw`$S = 1 + 2 + 3 + 4 + 5 + 6 + 7 + 8 + 9 + 10 + 11 + 12 + 13 + 14 + 15 + 16 + 17 + 18 + 19 + 20$`;

type Node = { props?: Record<string, unknown>; children?: unknown } | string | null;

/** Every left padding and left margin the drawn tree sets, in order. */
function insets(node: unknown, found: { padding: number[]; margin: number[] }): void {
  if (node == null || typeof node === "string") return;
  if (Array.isArray(node)) {
    for (const child of node) insets(child, found);
    return;
  }
  const n = node as Node & object;
  const style = [n.props?.style].flat(Infinity) as ({ paddingLeft?: unknown; marginLeft?: unknown } | null)[];
  for (const s of style) {
    if (s && typeof s.paddingLeft === "number") found.padding.push(s.paddingLeft);
    if (s && typeof s.marginLeft === "number" && s.marginLeft < 0) found.margin.push(s.marginLeft);
  }
  insets(n.children, found);
}

async function drawn(content: string) {
  const view = await render(<MarkdownContent content={content} />);
  const found = { padding: [] as number[], margin: [] as number[] };
  insets(view.toJSON(), found);
  return { found, scrolls: view.queryAllByTestId("math-text-scroll").length > 0 };
}

beforeEach(() => {
  jest.spyOn(Dimensions, "get").mockReturnValue({ width: 360, height: 780, scale: 3, fontScale: 1 });
});

afterEach(() => {
  jest.restoreAllMocks();
});

describe("fittedIndent", () => {
  it.each([
    // [formula width, indent kept] on a 360-point line (296 points for maths).
    [100, WORK_INDENT],
    [296 - WORK_INDENT, WORK_INDENT],
    [250, 46],
    [296, 0],
    [400, 0],
  ])("a formula %p wide keeps %p of the indent", (width, kept) => {
    expect(fittedIndent(WORK_INDENT, width, 360)).toBe(kept);
  });
});

describe("a working line under its heading", () => {
  it("keeps the whole indent when the formula fits after it", async () => {
    const { found, scrolls } = await drawn(`### 2. Divide by a\n\n${SHORT}`);
    expect(found.padding).toContain(WORK_INDENT);
    expect(scrolls).toBe(false);
  });

  it("moves a long formula left into the indent instead of past the right edge", async () => {
    const { found, scrolls } = await drawn(`### Factorial formula\n\n${FACTORIAL}`);
    expect(found.padding).not.toContain(WORK_INDENT);
    expect(scrolls).toBe(false);
  });

  it("scrolls only a formula wider than the whole line, from the margin", async () => {
    const { found, scrolls } = await drawn(`### Add them\n\n${VERY_LONG}`);
    expect(found.padding.filter((p) => p > 0 && p <= WORK_INDENT)).toEqual([]);
    expect(scrolls).toBe(true);
  });
});

describe("a display formula of the reply's own", () => {
  it("gives up its indent as it grows", async () => {
    const view = await render(<MarkdownContent content={`### Expand\n\n$$${FACTORIAL.slice(1, -1)}$$`} />);
    const found = { padding: [] as number[], margin: [] as number[] };
    insets(view.toJSON(), found);
    // Drawn (or loading) with its own indent: never more than the working column's.
    expect(found.padding.every((p) => p <= WORK_INDENT)).toBe(true);
  });
});

describe("a line of a worked solution", () => {
  const worked = (line: string) =>
    `**Given**\n\n$n = 4$\n\n**Required**\n\n$n!$\n\n**Solution**\n\n**Factorial formula**\n\n${line}\n\n**Answer**\n\n$24$`;

  it("keeps a short line in the working column", async () => {
    const { found, scrolls } = await drawn(worked(SHORT));
    expect(found.margin).toEqual([]);
    expect(scrolls).toBe(false);
  });

  it("moves a long line left into the indent, by no more than the indent", async () => {
    const { found, scrolls } = await drawn(worked(FACTORIAL));
    expect(found.margin).toHaveLength(1);
    expect(-found.margin[0]!).toBeGreaterThan(0);
    expect(-found.margin[0]!).toBeLessThanOrEqual(WORK_INDENT);
    expect(scrolls).toBe(false);
  });
});
