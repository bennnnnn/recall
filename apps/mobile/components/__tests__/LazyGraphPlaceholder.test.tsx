import { StyleSheet } from "react-native";
import { render, screen } from "@testing-library/react-native";

import { LazyFunctionGraphBlock } from "@/components/rich/LazyHeavyRich";
import { graphPlaceholderHeight } from "@/components/rich/graphPlaceholder";

// The graph's renderer never arrives here, so its placeholder stays on screen.
jest.mock("@/components/rich/FunctionGraphBlock", () => ({
  FunctionGraphBlock: () => {
    throw new Promise(() => {});
  },
}));

const NUMBER_LINE = JSON.stringify({ type: "number_line", expr: "x > 2", intervals: [] });
const TRAJECTORY = JSON.stringify({ type: "trajectory", expr: "v", points: [[0, 0], [1, 2], [2, 4]] });

function heldHeight(): number {
  return StyleSheet.flatten(screen.getByTestId("rich-load-placeholder").props.style).height as number;
}

describe("a graph's placeholder", () => {
  // A number line's answer sat under a tall gap sized for a function plot, a spinner in it.
  it("holds the room its own kind of graph takes", async () => {
    await render(<LazyFunctionGraphBlock content={NUMBER_LINE} />);
    expect(heldHeight()).toBe(graphPlaceholderHeight(NUMBER_LINE));
    expect(graphPlaceholderHeight(NUMBER_LINE)).toBe(118);
    expect(graphPlaceholderHeight(TRAJECTORY)).toBe(306);
    expect(graphPlaceholderHeight(JSON.stringify({ type: "trajectory", points: [[0, 0]] }))).toBe(258);
    expect(graphPlaceholderHeight("not json")).toBe(280);
  });

  it("is a quiet skeleton a screen reader hears as loading, not a bare spinner", async () => {
    await render(<LazyFunctionGraphBlock content={TRAJECTORY} />);
    expect(JSON.stringify(screen.toJSON())).not.toMatch(/ActivityIndicator/);
    expect(screen.getByRole("progressbar", { name: "common.loading" })).toBeTruthy();
  });
});
