// BUG FIX regression: the user's own sent message used to render as a bare
// <Text> with zero markdown/math processing, while the assistant's echoed
// version of the same content rendered fully (MarkdownContent handles both
// now). Sibling components pull in native modules (reanimated,
// expo-linear-gradient) unrelated to what this file tests — stubbed so
// import-time stays safe, mirroring markdownFenceRender.test.tsx's pattern.
import { render } from "@testing-library/react-native";

import { UserMessageContent } from "@/components/UserMessageContent";
import type { Message } from "@/lib/api/types";

jest.mock("@/components/ChatMessageImage", () => ({
  ChatMessageImage: "ChatMessageImage",
}));
jest.mock("@/components/ChatMessagePdf", () => ({
  ChatMessagePdf: "ChatMessagePdf",
}));
jest.mock("@/components/CollapsibleMessageBody", () => {
  const { View } = jest.requireActual("react-native");
  return {
    CollapsibleMessageBody: ({ children }: { children: React.ReactNode }) => (
      <View>{children}</View>
    ),
  };
});
// LinkPreviewCard (unrelated to math/markdown rendering) transitively pulls
// in expo-constants/expo-secure-store/network config — stub it directly
// rather than chasing that whole unrelated chain.
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
jest.mock("@/components/CodeBlock", () => {
  const { Text: RNText } = jest.requireActual("react-native");
  return {
    CodeBlock: ({ code, lang }: { code: string; lang: string }) => (
      <RNText>{`${lang}:${code}`}</RNText>
    ),
  };
});

function userMessage(content: string): Message {
  return {
    id: "m1",
    role: "user",
    content,
    model: null,
    created_at: new Date().toISOString(),
  };
}

describe("UserMessageContent math/markdown rendering", () => {
  it("renders a bare equation as typeset math, not literal text", async () => {
    const { getByText, queryByText } = await render(
      <UserMessageContent message={userMessage("x^2 + 2 = 6")} />,
    );

    // Superscript renders as a real Unicode superscript char via the same
    // no-WebView MathText fallback assistant content uses.
    expect(getByText("x² + 2 = 6")).toBeOnTheScreen();
    expect(queryByText("x^2 + 2 = 6")).toBeNull();
  });

  it("renders markdown emphasis instead of literal asterisks", async () => {
    const { getByText, queryByText } = await render(
      <UserMessageContent message={userMessage("**bold** text")} />,
    );

    expect(getByText("bold")).toBeOnTheScreen();
    expect(queryByText("**bold** text")).toBeNull();
  });

  it("still renders plain prose with no markdown syntax unchanged", async () => {
    const { getByText } = await render(
      <UserMessageContent message={userMessage("What time is it in Tokyo?")} />,
    );

    expect(getByText("What time is it in Tokyo?")).toBeOnTheScreen();
  });
});
