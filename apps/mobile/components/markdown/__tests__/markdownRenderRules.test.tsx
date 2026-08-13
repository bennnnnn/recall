import { StyleSheet, Text } from "react-native";
import { render } from "@testing-library/react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { makeRenderRules } from "@/components/markdown/markdownRenderRules";
import { makeMdStyles } from "@/components/markdown/markdownContentStyles";
import { lightTheme } from "@/lib/theme";

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
});
