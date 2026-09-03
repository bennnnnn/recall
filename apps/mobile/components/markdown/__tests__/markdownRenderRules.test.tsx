import { StyleSheet, Text } from "react-native";
import { render } from "@testing-library/react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { makeRenderRules } from "@/components/markdown/markdownRenderRules";
import { makeMdStyles } from "@/components/markdown/markdownContentStyles";
import { lightTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

jest.mock("@/components/LinkPreviewCard", () => ({
  LinkPreviewCard: "LinkPreviewCard",
}));
jest.mock("expo-clipboard", () => ({ setStringAsync: jest.fn() }));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("expo-haptics", () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  selectionAsync: jest.fn(),
}));
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  writeAsStringAsync: jest.fn(),
  EncodingType: { UTF8: "utf8" },
}));
jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("@/components/WebPreviewCodeBlock", () => ({
  WebPreviewCodeBlock: "WebPreviewCodeBlock",
}));
jest.mock("@/components/rich/CircularClockBlock", () => ({
  CircularClockBlock: "CircularClockBlock",
}));
jest.mock("@/components/rich/AnswerBlock", () => ({
  AnswerBlock: "AnswerBlock",
}));
jest.mock("@/components/CodeBlock", () => {
  const { Text: RNText } = jest.requireActual("react-native");
  return {
    CodeBlock: ({ code, lang }: { code: string; lang: string }) => (
      <RNText>{`${lang}:${code}`}</RNText>
    ),
  };
});

describe("markdown render rules", () => {
  it("clamps heading4–6 to body size so hierarchy never inverts", () => {
    const styles = makeMdStyles(lightTheme);
    expect(StyleSheet.flatten(styles.heading3)).toMatchObject({
      fontSize: 17,
      fontWeight: "700",
    });
    expect(StyleSheet.flatten(styles.heading4)).toMatchObject({
      fontSize: 16,
      fontWeight: "700",
    });
    expect(StyleSheet.flatten(styles.heading5)).toMatchObject({ fontSize: 16 });
    expect(StyleSheet.flatten(styles.heading6)).toMatchObject({ fontSize: 16 });
  });

  it("colors ordered-list markers and gives them a fixed rail", () => {
    const styles = makeMdStyles(lightTheme);
    expect(StyleSheet.flatten(styles.ordered_list_icon)).toMatchObject({
      color: lightTheme.textSecondary,
      minWidth: 22,
      textAlign: "right",
    });
  });

  it("zeros library block padding/border on inline code", () => {
    const styles = makeMdStyles(lightTheme);
    const inline = StyleSheet.flatten(styles.code_inline);
    expect(inline).toMatchObject({
      borderWidth: 0,
      padding: 0,
      backgroundColor: lightTheme.surfaceAlt,
      fontSize: 14,
      lineHeight: Type.body.lineHeight,
      paddingHorizontal: 4,
    });
    expect(inline.padding).not.toBe(10);
  });

  it("forwards strong children even when the node text contains math", () => {
    const { rules } = makeRenderRules(lightTheme);
    const child = <Text key="c">keep me</Text>;
    const element = rules.strong(
      { key: "s1", content: "keep me $x$" },
      child,
      [],
      { strong: { fontWeight: "700" } },
    );
    expect(element?.props.children).toBe(child);
  });

  it("keeps bold and a newline inside a markdown blockquote", async () => {
    const md = "> To be or not to be.\n> — Shakespeare";
    const { getByText } = await render(<MarkdownContent content={md} />);
    expect(getByText(/To be or not to be/)).toBeOnTheScreen();
    expect(getByText(/Shakespeare/)).toBeOnTheScreen();
  });

  it("promotes a quoted attribution paragraph into the quote card", async () => {
    const md =
      '"Courage is the most important of all the virtues because without courage, you can\'t practice any other virtue consistently." - Maya Angelou';
    const { getByText } = await render(<MarkdownContent content={md} />);
    expect(getByText(/Courage is the most important/)).toBeOnTheScreen();
    expect(getByText("— Maya Angelou")).toBeOnTheScreen();
  });

  it("does not paint a brand-blue left stripe on a quote card", async () => {
    const md =
      "> Courage is the most important of all the virtues, because without courage you can't practice any other virtue consistently. — Maya Angelou";
    const { getByText } = await render(<MarkdownContent content={md} />);
    const author = getByText("— Maya Angelou");
    let node: { parent?: unknown; props?: { style?: unknown } } | undefined =
      author;
    let sawPrimaryAccent = false;
    while (node) {
      const flat = StyleSheet.flatten(node.props?.style);
      if (flat?.borderLeftColor === lightTheme.primary) {
        sawPrimaryAccent = true;
        break;
      }
      node = node.parent as typeof node;
    }
    expect(sawPrimaryAccent).toBe(false);
  });

  it("keeps inline bold inside a blockquote", async () => {
    const { getByText } = await render(
      <MarkdownContent content={"> hello **world**"} />,
    );
    expect(getByText("world")).toBeOnTheScreen();
  });

  it("paints a trailing verification tick green", async () => {
    const { getByText } = await render(
      <MarkdownContent content={"0 + 3 = 3 ✓"} />,
    );
    const tick = getByText("✓");
    expect(StyleSheet.flatten(tick.props.style)).toMatchObject({
      color: lightTheme.success,
    });
  });

  it("keeps bold inline in a table cell instead of stacking", async () => {
    const md = [
      "| Feature | Value |",
      "| --- | --- |",
      "| Speed | plain **bold** more |",
    ].join("\n");
    const { getByText } = await render(<MarkdownContent content={md} />);
    const bold = getByText("bold");
    expect(bold).toBeOnTheScreen();
    const parent = bold.parent as { type?: string } | undefined;
    expect(parent?.type).not.toBe("View");
  });

  it("wraps a heading that contains bold", async () => {
    const { getByText } = await render(
      <MarkdownContent content="## Why **RevenueCat** is right" />,
    );
    expect(getByText("RevenueCat")).toBeOnTheScreen();
  });

  it("turns literal <br> in a table cell into a line break", async () => {
    const md = [
      "| Feature | Ethiopia | Kenya |",
      "| --- | --- | --- |",
      "| Famous For | Lucy fossils**<br>**Coffee | Safari<br>Runners |",
    ].join("\n");
    const { queryByText, getByText } = await render(
      <MarkdownContent content={md} />,
    );
    expect(queryByText(/<br/i)).toBeNull();
    expect(getByText(/Lucy fossils/)).toBeOnTheScreen();
    expect(getByText(/Coffee/)).toBeOnTheScreen();
  });

  it("does not paint a fill that differs from the chat background", async () => {
    const md = [
      "| Feature | Ethiopia | Kenya |",
      "| --- | --- | --- |",
      "| Capital | Addis Ababa | Nairobi |",
    ].join("\n");
    const { getByText } = await render(<MarkdownContent content={md} />);
    const fills = new Set<string>();
    const painted = [lightTheme.surface, lightTheme.surfaceAlt];
    for (const label of ["Feature", "Addis Ababa"]) {
      let node: { parent?: unknown; props?: { style?: unknown } } | undefined =
        getByText(label);
      while (node) {
        const flat = StyleSheet.flatten(node.props?.style);
        if (typeof flat?.backgroundColor === "string") {
          fills.add(flat.backgroundColor);
        }
        node = node.parent as typeof node;
      }
    }
    for (const color of painted) {
      expect(fills.has(color)).toBe(false);
    }
  });

  it("drops a stranded trailing colon after a nested-View math formula", async () => {
    // A line ending in "$...$:" with a sqrt (nested View) used to strand the
    // trailing ":" onto its own line ("random two dots" between the rule and
    // the next line). The colon is a redundant "leads to" marker once the
    // next line follows — it must not render as a lone ":".
    const { queryByText } = await render(
      <MarkdownContent content={String.raw`Use the product rule $\sqrt{ab}=\sqrt{a}\sqrt{b}$:`} />,
    );
    expect(queryByText(/^:$/)).toBeNull();
  });

  it("numbers nested bullets under a parent bullet so they scan as children", async () => {
    const md = `- **Powers**
  - eight squared is 64
  - eight cubed is 512`;
    const { getByText, queryByText } = await render(<MarkdownContent content={md} />);
    expect(getByText("1.")).toBeOnTheScreen();
    expect(getByText("2.")).toBeOnTheScreen();
    expect(getByText(/eight squared is 64/)).toBeOnTheScreen();
    expect(queryByText("3.")).toBeNull();
  });

  it("does not number a flat top-level bullet list", async () => {
    const md = `- Even number
- Composite number`;
    const { queryByText, getByText } = await render(<MarkdownContent content={md} />);
    expect(getByText(/Even number/)).toBeOnTheScreen();
    expect(queryByText("1.")).toBeNull();
    expect(queryByText("2.")).toBeNull();
  });
});
