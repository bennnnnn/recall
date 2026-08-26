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
  it("styles heading4–6 so they are not body-sized", () => {
    const styles = makeMdStyles(lightTheme);
    expect(StyleSheet.flatten(styles.heading4)).toMatchObject({
      fontSize: 15,
      fontWeight: "600",
    });
    expect(StyleSheet.flatten(styles.heading5)).toMatchObject({ fontSize: 14 });
    expect(StyleSheet.flatten(styles.heading6)).toMatchObject({ fontSize: 13 });
  });

  it("zeros library block padding/border on inline code", () => {
    const styles = makeMdStyles(lightTheme);
    const inline = StyleSheet.flatten(styles.code_inline);
    expect(inline).toMatchObject({
      borderWidth: 0,
      padding: 0,
      backgroundColor: lightTheme.surfaceAlt,
      fontSize: Type.body.fontSize,
      lineHeight: Type.body.lineHeight,
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
});
