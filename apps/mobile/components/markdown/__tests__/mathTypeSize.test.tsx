// A worked answer on an iPhone 17 Pro Max (2026-11-06): its maths was a size smaller
// than the words around it (16 against the reply's 18), "v₀ = 15 m/s (upward)" floated
// low beside its words and "h_max" sat above "Maximum height": a formula with a script
// is a View, and its row centred it on the line's box instead of setting it on the line.
import { render, within, type RenderResult } from "@testing-library/react-native";
import { StyleSheet, type TextStyle, type ViewStyle } from "react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { Type } from "@/lib/type";

jest.mock("@/components/LinkPreviewCard", () => ({
  LinkPreviewCard: "LinkPreviewCard",
}));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  writeAsStringAsync: jest.fn(),
  EncodingType: { UTF8: "utf8" },
}));
jest.mock("@/components/WebPreviewCodeBlock", () => ({
  WebPreviewCodeBlock: "WebPreviewCodeBlock",
}));
jest.mock("@/components/rich/CircularClockBlock", () => ({
  CircularClockBlock: "CircularClockBlock",
}));
jest.mock("@/components/rich/AnswerBlock", () => ({
  AnswerBlock: "AnswerBlock",
}));

type Styled = { props: { style?: unknown } };

function flat(node: Styled): TextStyle & ViewStyle {
  return StyleSheet.flatten(node.props.style as TextStyle) ?? {};
}

/** The size each formula's own text is set at: the empty run that carries its baseline. */
function formulaSizes(view: RenderResult): number[] {
  return view.getAllByTestId("math-baseline").map((node) => flat(node as unknown as Styled).fontSize ?? 0);
}

describe("inline maths reads at the size and on the line of its words", () => {
  it("sets a subscripted formula at the reply's text size, on the paragraph's baseline", async () => {
    const view = await render(
      <MarkdownContent content={String.raw`The ball leaves at $v_0 = 15\,\mathrm{m/s}$ (upward).`} />,
    );
    expect(formulaSizes(view)).toEqual([Type.reading.fontSize]);
    // The row sets every word and formula on one baseline: centred on the line's box, a
    // subscript pulled the formula up and an exponent pushed it down.
    expect(flat(view.getByTestId("md-math-inline-wrap"))).toMatchObject({ alignItems: "baseline" });
    // The formula's baseline is its own text's: an empty run in its face comes first.
    const tall = view.getByTestId("math-text-tall");
    expect(within(tall).getAllByTestId("math-baseline")).toHaveLength(1);
  });

  it("sets a formula led by a fraction on its text's baseline too", async () => {
    const view = await render(
      <MarkdownContent content={String.raw`So $\frac{1}{2}mv^2 = 40\,\mathrm{J}$ at the top.`} />,
    );
    expect(formulaSizes(view)).toEqual([Type.reading.fontSize]);
  });

  it("follows the text it sits in: a table cell's smaller size, a heading's larger one", async () => {
    const view = await render(
      <MarkdownContent
        content={["| quantity | value |", "| --- | --- |", String.raw`| speed | $v_0 = 3$ |`, "", String.raw`### The height $h_{max}$`].join("\n")}
      />,
    );
    expect(formulaSizes(view)).toEqual([Type.callout.fontSize, Type.h3.fontSize]);
  });

  it("sets the worked layout's Required line on its words' baseline", async () => {
    const view = await render(
      <MarkdownContent content={["**Required**  ", String.raw`$h_{max}$ — maximum height`].join("\n")} />,
    );
    const asked = view.getByTestId("workout-asked");
    expect(asked).toHaveTextContent(/maximum height/);
    expect(flat(asked)).toMatchObject({ alignItems: "baseline" });
    expect(formulaSizes(view)).toEqual([Type.reading.fontSize]);
  });
});
