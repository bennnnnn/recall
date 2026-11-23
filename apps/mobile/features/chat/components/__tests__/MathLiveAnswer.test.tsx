import { Dimensions, StyleSheet } from "react-native";
import { render } from "@testing-library/react-native";

import { MathLiveAnswer } from "@/features/chat/components/MathLiveAnswer";
import { DRAFT_TEXT_SIZE } from "@/lib/math/draftText";

// `t` that fills in `{{value}}`, so the screen reader's words can be checked.
jest.mock("react-i18next", () => {
  const words: Record<string, string> = { "chat.math_live_undefined": "undefined", "chat.math_live_answer_a11y": "Answer: {{value}}" };
  const t = (key: string, options?: { value?: string }) =>
    (words[key] ?? key).replace("{{value}}", options?.value ?? "");
  return { useTranslation: () => ({ t, i18n: { language: "en" }, ready: true }) };
});

type Node = { children: (Node | string)[] };
const text = (node: Node | string): string =>
  typeof node === "string" ? node : node.children.map(text).join("");

async function shown(input: string): Promise<string> {
  const { getByTestId } = await render(<MathLiveAnswer input={input} />);
  // MathText spaces with a thin space; read it as a plain one.
  return text(getByTestId("math-live-answer") as unknown as Node).replace(/\s+/g, " ");
}

type Styled = { props?: { style?: unknown }; children?: (Styled | string)[] | null };
const sizes = (node: Styled | string): number[] => {
  if (typeof node === "string") return [];
  const own = (StyleSheet.flatten(node.props?.style as never) as { fontSize?: number } | undefined)?.fontSize;
  return [...(own ? [own] : []), ...(node.children ?? []).flatMap(sizes)];
};

/** The largest text the answer draws: its digits' size. */
async function sizeOf(input: string): Promise<number> {
  const { getByTestId } = await render(<MathLiveAnswer input={input} />);
  return Math.max(...sizes(getByTestId("math-live-answer") as unknown as Styled));
}

type Scrolled = { props: { horizontal?: boolean; contentContainerStyle?: unknown }; children?: (Scrolled | string)[] | null };
const scrollsOf = (node: Scrolled | string): Scrolled[] =>
  typeof node === "string"
    ? []
    : [...(node.props.horizontal ? [node] : []), ...(node.children ?? []).flatMap(scrollsOf)];

const atTextSize = (fontScale: number) =>
  jest.spyOn(Dimensions, "get").mockReturnValue({ width: 390, height: 844, scale: 3, fontScale });

describe("MathLiveAnswer", () => {
  beforeEach(() => atTextSize(1));
  afterEach(() => jest.restoreAllMocks());

  it("tells a screen reader the value: undefined, or each branch", async () => {
    const label = async (input: string) => {
      const { getByTestId } = await render(<MathLiveAnswer input={input} />);
      return getByTestId("math-live-answer").props.accessibilityLabel as string;
    };
    expect(await label("$1\\div 0$")).toBe("Answer: undefined");
    expect(await label("$1\\pm 1$")).toBe("Answer: 1 - 1 = 0, 1 + 1 = 2");
  });

  it("keeps the branches when their values alone would be no lower", async () => {
    atTextSize(1.12);
    // Its values are fractions too: as tall as the branches, so the branches stay.
    expect(await shown("$\\frac{1}{2}\\pm 1$")).toMatch(/12 − 1 = −12/);
  });

  it("shows only the values when a larger text size makes the branches taller than the row", async () => {
    atTextSize(1.3);
    expect(await shown("$\\frac{-3\\pm\\sqrt{9-8}}{2}$")).toMatch(/^\W*= −2, −1$/);
  });

  it("scrolls an answer wider than its row sideways, centred while it fits", async () => {
    const { getByTestId } = await render(<MathLiveAnswer input={"$123456\\times 7\\pm 98765\\times 4$"} />);
    const [scroll] = scrollsOf(getByTestId("math-live-answer") as unknown as Scrolled);
    expect(scroll).toBeDefined();
    expect(StyleSheet.flatten(scroll!.props.contentContainerStyle as never)).toMatchObject({
      flexGrow: 1,
      alignItems: "center",
      justifyContent: "center",
    });
  });

  it("draws a value larger than the draft, and ± branches at the draft's own size", async () => {
    expect(await sizeOf("$2+1$")).toBe(20);
    expect(await sizeOf("$2\\pm 1$")).toBe(DRAFT_TEXT_SIZE);
  });

  it("writes out the branches of a ± draft that fits its row", async () => {
    expect(await shown("$2\\pm 1$")).toContain("2 − 1 = 1, 2 + 1 = 3");
    // A fraction in each branch is no taller than a fraction answer.
    const quadratic = await shown("$\\frac{-3\\pm\\sqrt{9-8}}{2}$");
    expect(quadratic).toContain("2 = −2,");
    expect(quadratic).not.toMatch(/^\W*=/);
  });

  it("shows only the values when the branches would be taller than the row", async () => {
    // A fraction in a fraction, echoed in each branch, is taller than the row holds.
    expect(await shown("$\\frac{1}{1+\\frac{1}{2}}\\pm 1$")).toContain("= −13, 53");
    // A raised power under the root lifts its bar past the row's top.
    expect(await shown("$\\frac{-3\\pm\\sqrt{3^{2}-4\\cdot 1\\cdot 2}}{2}$")).toMatch(/^\W*= −2, −1$/);
  });
});
