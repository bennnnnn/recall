import { render } from "@testing-library/react-native";
import { StyleSheet } from "react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { StepFlow } from "@/components/rich/StepFlow";
import { findLatexLeaks } from "@/lib/__tests__/support/latexLeaks";
import { parseSteps } from "@/lib/richBlocks";
import { Weight } from "@/lib/type";

jest.mock("@/lib/i18n", () => ({
  __esModule: true,
  default: {
    t: (key: string, args?: { n?: number; total?: number }) =>
      args ? `${key}:${args.n}/${args.total}` : key,
  },
}));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: () => null }));
// Display maths draws through MathJax asynchronously; its own tests cover it.
jest.mock("@/components/rich/MathSvgView", () => {
  const React = jest.requireActual("react");
  const { MathText } = jest.requireActual("@/components/rich/MathText");
  return {
    MathSvgView: ({ latex }: { latex: string }) => React.createElement(MathText, { latex }),
  };
});

type Node = { type: string; props: Record<string, unknown>; children: (Node | string)[] | null };

function visible(node: Node | Node[] | string | null): string {
  if (node == null) return "";
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(visible).join("");
  return (node.children ?? []).map(visible).join("");
}

// The arrows are hidden from screen readers, so queries look past that.
function arrows(view: Awaited<ReturnType<typeof render>>) {
  return view.getAllByTestId("step-flow-arrow", { includeHiddenElements: true });
}

// A lesson's method as the prompt asks for it (``teaching._LESSON_SHAPE``).
const BALANCING = [
  "1. **Count the atoms on each side**",
  "H₂ + O₂ → H₂O has 2 O on the left and 1 on the right.",
  "2. **Put a coefficient in front**",
  "A 2 before H₂O evens the oxygen: H₂ + O₂ → 2H₂O.",
  "3. **Recount and repeat**",
  "Now hydrogen is 2 against 4, so 2H₂ + O₂ → 2H₂O.",
].join("\n");

describe("StepFlow", () => {
  it("draws each step as a box, its title then its lines, joined by one arrow fewer", async () => {
    const view = await render(<StepFlow steps={parseSteps(BALANCING)} />);
    expect(view.getAllByTestId("step-flow-box")).toHaveLength(3);
    expect(arrows(view)).toHaveLength(2);
    expect(view.getByText("3")).toBeTruthy();
    expect(view.getByText("Count the atoms on each side")).toBeTruthy();
    expect(view.getByText("A 2 before H₂O evens the oxygen: H₂ + O₂ → 2H₂O.")).toBeTruthy();
  });

  it("sets the title in bold, even one written plain", async () => {
    const view = await render(<StepFlow steps={["Boil the water\nBring it to a rolling boil."]} />);
    const words = view.getByText("Boil the water");
    // Plain words sit in the styled line's own Text.
    const line = words.props.style ? words : words.parent!;
    expect(StyleSheet.flatten(line.props.style)).toMatchObject(Weight.semibold);
    expect(view.getByText("Bring it to a rolling boil.")).toBeTruthy();
    expect(view.queryAllByTestId("step-flow-arrow", { includeHiddenElements: true })).toHaveLength(0);
  });

  it("draws a bold title's code as code, not its backticks", async () => {
    const view = await render(<StepFlow steps={["**Read `2` at index `0`**\nWe need `7`."]} />);
    const seen = visible(view.toJSON() as unknown as Node);
    expect(seen).not.toContain("`");
    expect(seen).not.toContain("*");
    expect(view.getByText("2")).toBeTruthy();
  });

  it("reads each box as one element that says which step it is", async () => {
    const view = await render(<StepFlow steps={parseSteps(BALANCING)} />);
    const [first] = view.getAllByTestId("step-flow-box");
    expect(first!.props.accessible).toBe(true);
    expect(first!.props.accessibilityLabel).toBe(
      "rich.step_flow_a11y:1/3: Count the atoms on each side. H₂ + O₂ → H₂O has 2 O on the left and 1 on the right.",
    );
    // The arrows are drawing only: the labels say the order.
    expect(arrows(view)[0]!.props.accessibilityElementsHidden).toBe(true);
  });

  it("draws a step's maths as maths, never its source", async () => {
    const view = await render(
      <StepFlow steps={["**Add 9 to both sides**\n$x^2+6x+9 = 16$", "**Take the root**\n$x + 3 = \\pm 4$"]} />,
    );
    const seen = visible(view.toJSON() as unknown as Node);
    expect(seen).not.toContain("$");
    expect(findLatexLeaks(seen)).toEqual([]);
    expect(view.getAllByTestId("step-flow-box")[1]!.props.accessibilityLabel).not.toContain("\\");
  });

  it("is what a reply's ```steps card draws, a trace saved before it included", async () => {
    const trace = "```steps\n1. **Read `2` at index `0`**\nWe need `9 - 2 = 7`. Not seen yet, so save `2: 0`.\nDictionary: `{2: 0}`\n2. **Read `7` at index `1`**\n`9 - 7 = 2` is saved: return `[0, 1]`.\n```";
    const view = await render(<MarkdownContent content={`Here is the trace.\n\n${trace}`} />);
    expect(view.getAllByTestId("step-flow-box")).toHaveLength(2);
    expect(arrows(view)).toHaveLength(1);
    expect(view.getByText(/Dictionary:/)).toBeTruthy();
  });
});
