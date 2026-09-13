import { render } from "@testing-library/react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { IMPROPER_RESPONSE } from "../../../lib/__tests__/fixtures/improperIntegralResponse";

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
jest.mock("react-native-webview", () => {
  throw new Error("react-native-webview native module is not linked (test)");
});
jest.mock("@expo/dom-webview", () => {
  throw new Error("@expo/dom-webview native module is not linked (test)");
});
jest.mock("@/components/CodeBlock", () => {
  const { Text: RNText } = jest.requireActual("react-native");
  return {
    CodeBlock: ({ code, lang }: { code: string; lang: string }) => (
      <RNText>{`${lang}:${code}`}</RNText>
    ),
  };
});

type RenderNode = string | { children?: RenderNode[] | null } | RenderNode[] | null;
function visibleText(node: RenderNode): string {
  if (node == null) return "";
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(visibleText).join("");
  return (node.children ?? []).map(visibleText).join("");
}

describe("improper integral absolute-value rendering", () => {
  it.each([false, true])("preserves native math bars and nested list structure, streaming=%s", async (streaming) => {
    const { toJSON, queryByText } = await render(<MarkdownContent content={IMPROPER_RESPONSE} streaming={streaming} />);
    const visible = visibleText(toJSON());
    const compact = visible.replace(/\s+/g, "");
    expect(compact).toContain("ln|a|-ln|-1|");
    expect(compact).toContain("ln|1|-ln|b|");
    expect(compact).not.toContain("lnor");
    expect(visible).not.toContain("| ---");
    expect(queryByText(/\\ln|\\lim|\$/)).toBeNull();
  });
});
