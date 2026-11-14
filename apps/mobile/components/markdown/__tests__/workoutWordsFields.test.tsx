// A grade 12 run on the Galaxy S23 (2026-11-13): Required's "(c) $intervals$ (increasing and
// decreasing intervals)" drew "(c" on one line and ")" alone under it, and a part's title or a
// meaning written "as x → 5^+" showed its caret.
import { render } from "@testing-library/react-native";
import { StyleSheet } from "react-native";

import { MarkdownContent } from "@/components/MarkdownContent";

jest.mock("@/components/LinkPreviewCard", () => ({
  LinkPreviewCard: "LinkPreviewCard",
}));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("@/components/rich/AnswerBlock", () => ({
  AnswerBlock: "AnswerBlock",
}));

const REQUIRED = [
  "**Required**  ",
  "(a) $x_c$ (critical numbers)  ",
  "(c) $intervals$ (increasing and decreasing intervals)  ",
  "Part (b): $L^-$ (left-hand limit)  ",
  "$t$ (time of flight)  ",
  "$a$ (acceleration as the car turns)",
].join("\n");

describe("a worked reply's words fields", () => {
  it("keeps a part's letter whole before what the part asks", async () => {
    const view = await render(<MarkdownContent content={REQUIRED} />);
    const labels = view.getAllByTestId("workout-part-label");
    expect(labels.map((label) => [].concat(label.props.children).join(""))).toEqual(["(a) ", "(c) ", "Part (b): "]);
    for (const label of labels) {
      expect(StyleSheet.flatten(label.props.style)).toMatchObject({ flexShrink: 0 });
    }
    // The letter is drawn once, never again in the line it labels.
    expect(view.queryByText(/^\(c\)/)).toBe(labels[1]);
  });

  it("leaves a line with no part letter as it was", async () => {
    const view = await render(<MarkdownContent content={"**Required**  \n$t$ (time of flight)"} />);
    expect(view.queryAllByTestId("workout-part-label")).toEqual([]);
  });

  it.each([
    ["a part's title", "**(b) Left-hand limit as x → 5^-**\n\n**Substitution**  \n$L = 1$", "−"],
    ["a meaning", "**Required**  \n(a) $L^+$ (right-hand limit as x → 5^+)", "+"],
  ])("draws a power written in %s as a superscript", async (_where, content, sign) => {
    const view = await render(<MarkdownContent content={content} />);
    expect(view.queryByText(/\^/)).toBeNull();
    expect(view.getAllByTestId("math-script").map((node) => [].concat(node.props.children).join(""))).toContain(sign);
  });

  it.each([
    "**Required**  \n$f$ (the file_name field)",
    "**Required**  \n$n$ (lines of C++ code)",
  ])("leaves words with an underscore or a plus in %s", async (content) => {
    const view = await render(<MarkdownContent content={content} />);
    expect(view.getByText(/file_name|C\+\+/)).toBeOnTheScreen();
  });
});
