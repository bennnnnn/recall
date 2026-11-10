/**
 * The function plot card and its full-screen explorer, rendered directly:
 * the card's size and title, the series editor in the card and then in the
 * explorer, hole markers, the explorer's own plot size, and the Skia canvas
 * with the SVG one standing in while it loads.
 */
import { act, fireEvent, render, renderHook } from "@testing-library/react-native";
import { ScrollView, StyleSheet, type LayoutChangeEvent } from "react-native";

import { InteractiveFunctionPlot } from "@/components/rich/InteractiveFunctionPlot";
import { useFunctionPlotState } from "@/components/rich/useFunctionPlotState";
import { parseGraphSpec, type GraphSpec } from "@/lib/math/graphSpec";
import { lightTheme } from "@/lib/theme";

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 20, bottom: 10, left: 0, right: 0 }),
}));
let mockSkia = false;
jest.mock("@/lib/skiaAvailability", () => ({ isSkiaAvailable: () => mockSkia }));
jest.mock("@/ui/icons/Icon", () => ({ Icon: () => null }));

type RenderNode = { type?: string; props?: Record<string, unknown>; children?: unknown[] | null };

function nodesIn(value: unknown): RenderNode[] {
  if (Array.isArray(value)) return value.flatMap(nodesIn);
  if (!value || typeof value !== "object") return [];
  const node = value as RenderNode;
  return [node, ...(node.children ?? []).flatMap(nodesIn)];
}

const STYLES = { wrap: { marginVertical: 4 }, title: { color: "#111111" } };

function spec(fence: Record<string, unknown>): GraphSpec {
  const parsed = parseGraphSpec(JSON.stringify(fence));
  if (!parsed) throw new Error("expected the fence to parse");
  return parsed;
}

const PARABOLA = spec({
  type: "function",
  expr: "x**2",
  points: [
    [-2, 4],
    [-1, 1],
    [0, 0],
    [1, 1],
    [2, 4],
  ],
});

function plot(graph: GraphSpec, chartWidth = 300) {
  return render(<InteractiveFunctionPlot spec={graph} chartWidth={chartWidth} styles={STYLES} theme={lightTheme} />);
}

/** A tap on a curve's maths, as a person edits it: the field takes its place. */
async function edit(view: Awaited<ReturnType<typeof plot>>, id = "graph-expr-input") {
  await fireEvent.press(view.getByTestId(`${id}-math`));
  return view.getByTestId(id);
}

beforeEach(() => {
  mockSkia = false;
});

describe("InteractiveFunctionPlot", () => {
  it("sizes the card's plot to the chart less its inset, then to its laid-out width", async () => {
    const { getByTestId } = await plot(PARABOLA);
    const press = () => StyleSheet.flatten(getByTestId("graph-expand").props.style);
    expect(press().width).toBe(276);
    expect(press().height).toBe(220);
    await fireEvent(getByTestId("graph-card"), "layout", { nativeEvent: { layout: { width: 340, height: 300 } } });
    expect(press().width).toBe(316);
    // A width that rounds to the same size, or to nothing, keeps the plot as it is.
    await fireEvent(getByTestId("graph-card"), "layout", { nativeEvent: { layout: { width: 340.2, height: 300 } } });
    await fireEvent(getByTestId("graph-card"), "layout", { nativeEvent: { layout: { width: 10, height: 300 } } });
    expect(press().width).toBe(316);
  });

  it("titles a custom title, never a title that repeats the expression", async () => {
    const titled = await plot(spec({ type: "function", expr: "x**2", title: "Area x**2", points: [[0, 0], [1, 1]] }));
    expect(titled.getByText("Area x²")).toBeOnTheScreen();
    const plain = await plot(spec({ type: "function", expr: "x**2", title: "x**2", points: [[0, 0], [1, 1]] }));
    expect(plain.queryByText("x²")).toBeNull();
    expect(plain.getByLabelText("rich.graph_expr_a11y, y = x^2")).toBeOnTheScreen();
  });

  it("titles a vertical line and offers no editor for it", async () => {
    const { getByText, queryByTestId } = await plot(spec({ type: "vertical", expr: "x = 3", x: 3 }));
    expect(getByText("x = 3")).toBeOnTheScreen();
    expect(queryByTestId("graph-expr-input")).toBeNull();
    expect(queryByTestId("graph-expr-input-math")).toBeNull();
    expect(queryByTestId("graph-add-function")).toBeNull();
  });

  it("draws the legend as maths, and the field in its place while it is edited", async () => {
    // The legend read `y = x^2 - 4x + 3` in a monospace field (2026-11-06). The field lay
    // under the maths with its text transparent, which Android drew anyway (S23, 2026-11-09).
    const view = await plot(
      spec({ type: "function", expr: "x**2 - 4*x + 3", points: [[0, 3], [2, -1], [4, 3]] }),
    );
    const { getByTestId, queryByTestId } = view;
    const math = getByTestId("graph-expr-input-math");
    // Typeset: a raised 2 and a true minus sign; a button a tap or a screen reader reaches.
    expect(math).toHaveTextContent(/y = x2 − 4x \+ 3$/);
    expect(math.props.accessibilityRole).toBe("button");
    expect(math.props.accessibilityLabel).toBe("rich.graph_expr_a11y, y = x^2 - 4*x + 3");
    // No field under it, to show through.
    expect(queryByTestId("graph-expr-input")).toBeNull();
    const field = await edit(view);
    expect(queryByTestId("graph-expr-input-math")).toBeNull();
    // The plotting grammar's text, for editing, with the keyboard up at once.
    expect(field.props.value).toBe("y = x^2 - 4*x + 3");
    expect(field.props.autoFocus).toBe(true);
    expect(StyleSheet.flatten(field.props.style).color).toBe(lightTheme.text);
    await fireEvent(field, "blur");
    expect(getByTestId("graph-expr-input-math")).toBeOnTheScreen();
    // What the plot cannot read stays the text it is, in the danger ink.
    await fireEvent.changeText(await edit(view), "banana");
    await fireEvent(getByTestId("graph-expr-input"), "blur");
    expect(queryByTestId("graph-expr-input-math")).toBeNull();
    expect(StyleSheet.flatten(getByTestId("graph-expr-input").props.style).color).toBe(lightTheme.danger);
  });

  it("adds, hides and removes a series in the card", async () => {
    const { getByTestId, queryByTestId } = await plot(PARABOLA);
    await fireEvent.press(getByTestId("graph-add-function"));
    await fireEvent.changeText(getByTestId("graph-expr-input-1"), "2x");
    expect(getByTestId("graph-expr-input-1").props.value).toBe("2x");
    // Hidden while it is typed, the field dims; once typed, its maths does.
    const opacity = (id: string) => StyleSheet.flatten(getByTestId(id).props.style).opacity;
    await fireEvent.press(getByTestId("graph-hide-1"));
    expect(opacity("graph-expr-input-1")).toBe(0.4);
    await fireEvent(getByTestId("graph-expr-input-1"), "blur");
    expect(opacity("graph-expr-input-1-math")).toBe(0.4);
    await fireEvent.press(getByTestId("graph-hide-1"));
    expect(opacity("graph-expr-input-1-math")).toBeUndefined();
    await fireEvent.press(getByTestId("graph-remove-1"));
    expect(queryByTestId("graph-expr-input-1")).toBeNull();
    // The seeded expression is locked: it has no hide or remove buttons.
    expect(queryByTestId("graph-hide-0")).toBeNull();
  });

  it("marks holes while the seeded expression stands, and drops them once it is edited", async () => {
    const holed = spec({
      type: "function",
      expr: "(x**2-1)/(x-1)",
      points: [[-2, -1], [0, 1], [2, 3]],
      holes: [[1, 2]],
    });
    const view = await plot(holed);
    const { getByTestId, queryByTestId } = view;
    expect(getByTestId("graph-hole-0")).toBeOnTheScreen();
    await fireEvent.changeText(await edit(view), "x + 1");
    expect(queryByTestId("graph-hole-0")).toBeNull();
  });

  it("labels the points the fence marks, and drops them once the curve is edited", async () => {
    // y = x² − 4x + 3 showed the curve only, though the reply named its roots, vertex and
    // y-intercept (2026-11-06). SymPy's points arrive in the fence and are drawn as sent.
    const marked = spec({
      type: "function",
      expr: "x**2 - 4*x + 3",
      points: [[-1, 8], [0, 3], [1, 0], [2, -1], [3, 0], [4, 3], [5, 8]],
      marks: [
        { x: 1, y: 0, label: "(1, 0)" },
        { x: 3, y: 0 },
        { x: 2, y: -1, label: "vertex (2, −1)" },
        { x: 0, y: 3, label: "(0, 3)" },
        { x: "2", y: 1 },
      ],
    });
    const view = await plot(marked);
    const { queryByTestId, toJSON } = view;
    // react-native-svg's text is a native RNSVGTSpan holding `content`.
    const nodes = nodesIn(toJSON());
    const label = (i: number) =>
      nodesIn(nodes.find((node) => node.props?.testID === `graph-mark-label-${i}`))
        .filter((node) => node.type === "RNSVGTSpan")
        .map((node) => String(node.props?.content ?? ""))
        .join("");
    expect(label(0)).toBe("(1, 0)");
    // A mark with no label of its own is labelled with its coordinates.
    expect(label(1)).toBe("(3, 0)");
    expect(label(2)).toBe("vertex (2, −1)");
    expect(label(3)).toBe("(0, 3)");
    // A malformed mark is left out, never the graph.
    expect(queryByTestId("graph-mark-4")).toBeNull();
    await fireEvent.changeText(await edit(view), "x + 1");
    expect(queryByTestId("graph-mark-0")).toBeNull();
  });

  it("keeps the explorer's view when the keyboard shrinks its plot", async () => {
    // Re-made for each plot height, the view jumped back to its start when the keyboard came
    // up to type a function, throwing the user's pan and zoom away (review, 2026-11-09).
    const { result } = await renderHook(() => useFunctionPlotState(PARABOLA, 300, lightTheme));
    const layout = (height: number) =>
      act(async () => {
        result.current.explorer.onPlotLayout({
          nativeEvent: { layout: { x: 0, y: 0, width: 360, height } },
        } as LayoutChangeEvent);
      });
    await layout(600);
    const view = result.current.explorer.initialView;
    await layout(260);
    expect(result.current.explorer.plot.height).toBe(260);
    expect(result.current.explorer.initialView).toEqual(view);
  });

  it("takes the explorer's view from its tallest plot, not a first one the keyboard shortened", async () => {
    // Opened while a keyboard was still closing, the plot first laid out short, and the view
    // kept that shape after the keyboard went: stretched for good (review, 2026-11-09).
    const { result } = await renderHook(() => useFunctionPlotState(PARABOLA, 300, lightTheme));
    const layout = (height: number) =>
      act(async () => {
        result.current.explorer.onPlotLayout({
          nativeEvent: { layout: { x: 0, y: 0, width: 360, height } },
        } as LayoutChangeEvent);
      });
    await layout(260);
    const short = result.current.explorer.initialView;
    await layout(600);
    const full = result.current.explorer.initialView;
    expect(full).not.toEqual(short);
    await layout(260);
    expect(result.current.explorer.initialView).toEqual(full);
  });

  it("opens the explorer on its fitted window each time, not where the last pinch left it", async () => {
    // 2026-11-10: the explorer opened zoomed far out, a thin spike, after an earlier pinch.
    const { result } = await renderHook(() => useFunctionPlotState(PARABOLA, 300, lightTheme));
    await act(async () => {
      result.current.explorer.onPlotLayout({
        nativeEvent: { layout: { x: 0, y: 0, width: 344, height: 480 } },
      } as LayoutChangeEvent);
    });
    const fitted = result.current.explorer.initialView;
    // The SVG view follows the window fitted to the laid-out plot, as the Skia one does.
    expect(result.current.explorer.viewport.bounds).toEqual(fitted);
    await act(async () => { result.current.openExplorer(); });
    await act(async () => {
      result.current.explorer.viewport.commitBounds({ xMin: -50, xMax: 50, yMin: -80, yMax: 80 });
    });
    await act(async () => { result.current.closeExplorer(); });
    await act(async () => { result.current.openExplorer(); });
    expect(result.current.explorer.viewport.bounds).toEqual(fitted);
  });

  it("moves the editor into the explorer while it is open, and back when it closes", async () => {
    const { getByTestId, getAllByTestId, queryByTestId } = await plot(PARABOLA);
    expect(queryByTestId("graph-modal-sheet")).toBeNull();
    expect(queryByTestId("graph-series-scroll")).toBeNull();
    await fireEvent.press(getByTestId("graph-expand"));
    expect(getByTestId("graph-modal-sheet")).toBeOnTheScreen();
    expect(getAllByTestId("graph-expr-input-math")).toHaveLength(1);
    expect(getByTestId("graph-series-scroll")).toBeOnTheScreen();
    const sheet = StyleSheet.flatten(getByTestId("graph-modal-sheet").props.style);
    expect(sheet.marginTop).toBe(20);
    expect(sheet.paddingBottom).toBe(10);
    expect(sheet.backgroundColor).toBe(lightTheme.elevated);
    await fireEvent.press(getByTestId("graph-close"));
    expect(queryByTestId("graph-modal-sheet")).toBeNull();
    expect(getByTestId("graph-expr-input-math")).toBeOnTheScreen();
    expect(queryByTestId("graph-series-scroll")).toBeNull();
  });

  it("scrolls an added series into view in the explorer", async () => {
    const scrollToEnd = jest.spyOn(ScrollView.prototype, "scrollToEnd").mockImplementation(() => undefined);
    const frame = jest.spyOn(globalThis, "requestAnimationFrame").mockImplementation((callback) => {
      callback(0);
      return 0;
    });
    try {
      const { getByTestId } = await plot(PARABOLA);
      await fireEvent.press(getByTestId("graph-add-function"));
      expect(scrollToEnd).not.toHaveBeenCalled();
      await fireEvent.press(getByTestId("graph-expand"));
      await fireEvent.press(getByTestId("graph-add-function"));
      expect(getByTestId("graph-expr-input-2")).toBeOnTheScreen();
      expect(scrollToEnd).toHaveBeenCalledWith({ animated: true });
    } finally {
      scrollToEnd.mockRestore();
      frame.mockRestore();
    }
  });

  it("sizes the explorer's plot to its laid-out box", async () => {
    const { getByTestId, getByLabelText, toJSON } = await plot(PARABOLA);
    await fireEvent.press(getByTestId("graph-expand"));
    const surface = getByLabelText("rich.graph_plot_a11y");
    await fireEvent(surface, "layout", { nativeEvent: { layout: { width: 333.4, height: 411.6 } } });
    const tree = JSON.stringify(toJSON());
    expect(tree).toContain('"width":333');
    expect(tree).toContain('"height":412');
  });

  it("draws on Skia when it is available, with the SVG plot standing in while it loads", async () => {
    mockSkia = true;
    const { getByTestId, findByTestId, queryByTestId } = await plot(PARABOLA);
    expect(queryByTestId("skia-graph-card") ?? getByTestId("graph-expand")).toBeOnTheScreen();
    expect(await findByTestId("skia-graph-card")).toBeOnTheScreen();
    await fireEvent.press(getByTestId("graph-expand"));
    expect(getByTestId("graph-interaction-surface")).toBeOnTheScreen();
    await act(async () => {});
    expect(getByTestId("skia-graph-canvas")).toBeOnTheScreen();
  });
});
