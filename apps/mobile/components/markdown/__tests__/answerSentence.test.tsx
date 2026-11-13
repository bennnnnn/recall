/**
 * An answer written as a sentence round its maths is no boxed value (the textbook run,
 * 2026-11-13): "A line from (−3, −5) to (3, 7) — slope 2, y-intercept 1" was drawn in the
 * answer's box, its words after the dash above it as a move. A box holds the answer's value;
 * the sentence stays a line of its own, read whole.
 */
import { cleanup, render } from "@testing-library/react-native";

import { MarkdownContent } from "@/components/MarkdownContent";

jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: () => null }));

describe("an answer written as a sentence", () => {
  it.each([
    "**Answer**\nA line from $(-3, -5)$ to $(3, 7)$ — slope $2$, $y$-intercept $1$.",
    "**Answer**  \nThe ball lands $x = 12\\,\\mathrm{m}$ from the wall.",
    "**Answer**  \nThe line has slope $2$ and passes through $(0, 1)$.",
  ])("draws no box round %s", async (content) => {
    const screen = await render(<MarkdownContent content={content} />);
    expect(screen.queryByTestId("workout-answer")).toBeNull();
    // Read whole: its dash is the sentence's, never a move's note above it.
    expect(screen.queryByTestId("workout-move")).toBeNull();
    expect(screen.getByTestId("workout-line")).toBeOnTheScreen();
    await cleanup();
  });

  it.each([
    ["**Answer**  \n$c = 15\\ \\text{cm}$", /c = 15/],
    ["**Answer**  \nSpeed = 4 m/s", /Speed = 4/],
    ["**Answer**  \nTotal area: $A = 24$", /A = 24/],
    ["**Answer**  \n$5^\\circ$ from the normal", /5/],
    ["**Answer**  \n$x = 3$  \nOnly the positive root counts.", /x = 3/],
    ["**Answer**  \nParis", /Paris/],
  ])("boxes the value of %s", async (content, value) => {
    const screen = await render(<MarkdownContent content={content} />);
    expect(screen.getByTestId("workout-answer")).toHaveTextContent(value);
    await cleanup();
  });
});
