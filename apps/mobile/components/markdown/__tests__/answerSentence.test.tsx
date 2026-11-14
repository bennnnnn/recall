/**
 * More than one sentence is no boxed value (the textbook run, 2026-11-13): "A line from
 * (−3, −5) to (3, 7) — slope 2, y-intercept 1" was drawn in the answer's box, its words after
 * the dash above it as a move: "slope 2, y-intercept 1. A line from …", two sentences. They
 * stay a line of their own, read whole. One sentence is boxed whatever its words.
 */
import { cleanup, render } from "@testing-library/react-native";

import { MarkdownContent } from "@/components/MarkdownContent";

jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: () => null }));

describe("an answer written as a sentence", () => {
  it.each([
    "**Answer**\nA line from $(-3, -5)$ to $(3, 7)$ — slope $2$, $y$-intercept $1$.",
    "**Answer**  \n" + String.raw`Slope $2$, $y$-intercept $1$. A line from $(-3, -5)$ to $(3, 7)$.`,
    "**Answer**  \n" + String.raw`The line has slope $2$. It passes through $(0, 1)$.`,
    "**Answer**  \n" + String.raw`La recta tiene pendiente $2$. Pasa por $(0, 1)$.`,
  ])("draws no box round %s", async (content) => {
    for (const streaming of [false, true]) {
      const screen = await render(<MarkdownContent content={content} streaming={streaming} />);
      expect(screen.queryByTestId("workout-answer")).toBeNull();
      // Read whole: its dash is the sentence's, never a move's note above it.
      expect(screen.queryByTestId("workout-move")).toBeNull();
      expect(screen.getByTestId("workout-line")).toBeOnTheScreen();
      await cleanup();
    }
  });

  it.each(
    [
      String.raw`The speed is $20$ meters per second`,
      String.raw`You need $2.5$ kilograms of flour`,
      String.raw`It takes $3$ hours and $20$ minutes`,
      String.raw`The tank holds $450$ litres of water`,
      String.raw`The angle is $36.9^\circ$ above the horizontal`,
      String.raw`She needs $7$ more cupcakes for the party`,
      String.raw`La velocidad es $20$ metros por segundo`,
      String.raw`The answer is $\frac{3}{4}$ of the whole pizza`,
      String.raw`Both $3$ and $-2$ satisfy the equation.`,
      String.raw`$\triangle ABC \cong \triangle DEF$ by the SAS rule here`,
      String.raw`The area is $A = 24$ cm²`,
      String.raw`Sum of the angles $= 180°$`,
      String.raw`The hypotenuse $c = 15\ \text{cm}$`,
      String.raw`Roots are $x = 3$ and $x = -2$`,
      String.raw`The line has slope $2$ and passes through $(0, 1)$.`,
      String.raw`The monthly payment is $386.66.`,
      "$c = 15\\ \\text{cm}$",
      "Speed = 4 m/s",
      "Total area: $A = 24$",
      "Carbon dioxide",
      "New York",
      "Not possible",
      "Only the positive root counts.",
    ].map((line) => [`**Answer**  \n${line}`]),
  )("boxes the value of %s", async (content) => {
    const screen = await render(<MarkdownContent content={content} />);
    expect(screen.getByTestId("workout-answer")).toBeOnTheScreen();
    await cleanup();
  });
});
