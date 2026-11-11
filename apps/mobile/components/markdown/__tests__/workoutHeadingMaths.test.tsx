/**
 * A worked reply's headings and notes draw their maths as maths (2026-11-11 phone test):
 * "**Substitution x = \tan t formula**" showed its dollars and `\tan` as text, because a
 * heading inside Solution was drawn as plain text. A formula with no name sits under
 * **Solution**, drawn as working (no rule, the maths column), never under a bare
 * **Formula**.
 */
import { StyleSheet } from "react-native";
import { render } from "@testing-library/react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { WORK_INDENT } from "@/components/markdown/markdownContentStyles";
import { findLatexLeaks } from "@/lib/__tests__/support/latexLeaks";
import { normalizeBoldInlineMath } from "@/lib/markdown/preprocess";

jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: () => null }));

/** The text a reader sees, the pieces in order. */
function seen(node: unknown): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(seen).join("");
  return ((node as { children?: unknown[] }).children ?? []).map(seen).join("");
}

// The saved reply to "Evaluate ∫₀¹ ln(1+x)/(1+x²) dx" (DeepSeek, 2026-11-11), as stored.
const SAVED_INTEGRAL = [
  "**Given**  \n$I = \\int_0^1 \\frac{\\ln(1+x)}{1+x^2}\\,dx$  \nwhere $I$ = definite integral",
  "**Required**  \n$I$ (value of the definite integral)",
  "**Solution**",
  "**Substitution x = \\tan t formula**  \n$I = \\int_0^{\\pi/4} \\ln(1+\\tan t)\\,dt$  \n" +
    "$\\int_0^{\\pi/4} \\ln\\cos t\\,dt = \\int_0^{\\pi/4}\\ln\\cos t\\,dt$ — evenness of \\ln\\cos t",
  "**Substitution**  \n$I = \\frac{\\pi}{8}\\ln 2$",
].join("\n\n");

describe("maths in a worked heading", () => {
  it.each([
    ["the saved reply, maths left bare in its heading", SAVED_INTEGRAL],
    [
      "the server's layout, the heading ending on its maths",
      SAVED_INTEGRAL.replace("**Substitution x = \\tan t formula**", "**Substitution $x = \\tan t$**"),
    ],
    [
      "a model's own heading over its lines",
      "**Given**  \n$m$\n\n**Solution**\n\n**Solve for $v$**\n$v = \\sqrt{\\frac{g}{k}}$",
    ],
  ])("is drawn as maths: %s", async (_name, content) => {
    const screen = await render(<MarkdownContent content={content} />);
    const text = seen(screen.toJSON());
    expect(findLatexLeaks(text)).toEqual([]);
    const headings = screen.getAllByTestId("workout-subheading");
    expect(headings.length).toBeGreaterThan(0);
    // The heading's maths is drawn by the maths renderer, a piece of the heading beside
    // its words, and no source shows in it.
    const heading = headings[0]!;
    expect(heading.children.length).toBeGreaterThan(1);
    expect(seen(heading)).toMatch(/tan\W*t|v/);
    expect(seen(heading)).not.toMatch(/[$\\]/);
  });

  it("keeps a plain heading as text", async () => {
    const screen = await render(
      <MarkdownContent
        content={"**Given**  \n$d = 3$\n\n**Solution**\n\n**Average speed formula**  \n$v = \\frac{d}{t}$"}
      />,
    );
    expect(screen.getByTestId("workout-subheading").props.children).toBe("Average speed formula");
  });
});

describe("a formula with no name", () => {
  it("sits under Solution as working: no rule, the maths column, Solve for as a heading", async () => {
    const content = [
      "**Given**  \n$k = 400\\,\\mathrm{N/m}$",
      "**Required**  \n$x$ (maximum compression)",
      "**Solution**",
      "$m g h = \\frac{1}{2} k x^{2}$  \nSolve for $x$  \n$x = \\sqrt{\\frac{2 m g h}{k}}$",
      "**Substitution**  \n$x = 0.71\\,\\mathrm{m}$",
    ].join("\n\n");
    const screen = await render(<MarkdownContent content={content} />);
    expect(screen.queryByText("Formula")).toBeNull();
    expect(screen.getAllByTestId("workout-heading").map((node) => seen(node))).toEqual([
      "Given",
      "Required",
      "Solution",
    ]);
    const bodies = screen.getAllByTestId("workout-body").map((node) => StyleSheet.flatten(node.props.style));
    // Given and Required behind their rule; Solution's lines at the working column, no rule.
    expect(bodies[2]!.borderLeftWidth ?? 0).toBe(0);
    expect(bodies[2]!.paddingLeft).toBe(WORK_INDENT);
    expect(screen.getAllByTestId("workout-subheading").map((node) => seen(node))).toEqual([
      "Solve for x",
      "Substitution",
    ]);
  });
});

describe("bold maths in a worked reply", () => {
  it("keeps a heading line whole, over the lines below it", () => {
    const heading = "**Substitution $x = \\tan t$**\n$I = 1$";
    expect(normalizeBoldInlineMath(heading, true)).toBe(heading);
  });

  it.each([
    // Not worked: the maths leaves the bold as before.
    ["**Answer: $x = 2$**\n$x = 2$", false, "**Answer:** $x = 2$\n$x = 2$"],
    // Worked, but a line alone with nothing under it, or bold that is only maths.
    ["**Answer: $x = 2$**", true, "**Answer:** $x = 2$"],
    ["**$x^2$**\n$x = 2$", true, "$x^2$\n$x = 2$"],
    // Worked, but in a sentence: not a heading.
    ["So **the answer is $x = 2$** here.\n$x = 2$", true, "So **the answer is** $x = 2$ here.\n$x = 2$"],
  ])("unwraps any other bold maths: %s", (text, worked, expected) => {
    expect(normalizeBoldInlineMath(text, worked)).toBe(expected);
  });
});
