// BUG FIX regression: list items like "An **open circle at 0**" used to put
// "An" on its own line. paragraph was a View and textgroup a Fragment, so
// each text/strong/em became a full-width Text block.
import { render } from "@testing-library/react-native";
import { Text } from "react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { makeRenderRules } from "@/components/markdown/markdownRenderRules";
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

const LIST = [
  "- An **open circle at 0** (since 0 is *not* included)",
  "- A **ray extending left** → toward negative infinity",
].join("\n");

describe("markdown paragraph wrap", () => {
  it("renders a list paragraph as Text, not a View", () => {
    const { rules } = makeRenderRules(lightTheme);
    const element = rules.paragraph(
      { key: "p1" },
      [
        <Text key="a">An </Text>,
        <Text key="b">open circle at 0</Text>,
      ],
      [],
      { body: {}, text: {}, paragraphRun: {} },
    );
    expect(element?.type).toBe(Text);
  });

  it("still parses mixed bold/italic list copy", async () => {
    const { getByText } = await render(<MarkdownContent content={LIST} />);

    expect(getByText(/An/)).toBeOnTheScreen();
    expect(getByText("open circle at 0")).toBeOnTheScreen();
    expect(getByText(/^\s*A\s*$/)).toBeOnTheScreen();
    expect(getByText("ray extending left")).toBeOnTheScreen();
    expect(getByText("not")).toBeOnTheScreen();
  });
});
