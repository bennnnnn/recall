// A student's "lim_{x→5⁺}" (2026-11-13): a script with a script of its own is a box, and its
// runs stood in a column, x over → over 5 over +.
import { render } from "@testing-library/react-native";
import { StyleSheet } from "react-native";

import { MathText } from "@/components/rich/MathText";

describe("a script with a body of its own", () => {
  it.each([
    "lim_{x→5⁺}",
    String.raw`e^{x + y^{2}}`,
    String.raw`a_{n+1}^{2^k}`,
  ])("lays %s's script out in a row", async (latex) => {
    const screen = await render(<MathText latex={latex} />);
    const boxes = screen.getAllByTestId("math-script").filter((node) => node.type === "View");
    expect(boxes.length).toBeGreaterThan(0);
    for (const box of boxes) {
      expect(StyleSheet.flatten(box.props.style)).toMatchObject({ flexDirection: "row" });
    }
  });
});
