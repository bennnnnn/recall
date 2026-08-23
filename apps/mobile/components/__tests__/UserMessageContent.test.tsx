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

  it("spaces a bare unspaced equation the user typed", async () => {
    const { getByText } = await render(
      <UserMessageContent message={userMessage("x=3")} />,
    );
    expect(getByText("x=3")).toBeOnTheScreen();
  });

  it("shows 6\\sqrt{4} as typed, not a 6th root", async () => {
    const { queryByText, getByTestId } = await render(
      <UserMessageContent message={userMessage("$6\\sqrt{4}$")} />,
    );
    expect(queryByText(/√\[6\]/)).toBeNull();
    expect(queryByText(/\\times/)).toBeNull();
    expect(getByTestId("math-draft-preview")).toBeOnTheScreen();
  });

  it("does not format $|5|3$ into a markdown table", async () => {
    const { getByTestId, queryByText, queryByTestId } = await render(
      <UserMessageContent message={userMessage("$|5|3$")} />,
    );
    expect(getByTestId("math-draft-preview")).toBeOnTheScreen();
    expect(getByTestId("math-abs")).toBeOnTheScreen();
    expect(queryByText("---")).toBeNull();
    expect(queryByTestId("math-slot-before-caret")).toBeNull();
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

  it("BUG FIX regression: sent bare equation does not use math draft preview (only $-delimited)", async () => {
    // Sent messages with bare equations (no $) should NOT render via
    // MathDraftPreview — they go through the normal markdown path.
    // Only $-delimited math uses the draft preview for sent messages.
    const { queryByTestId } = await render(
      <UserMessageContent message={userMessage("x^2 = 4")} />,
    );
    expect(queryByTestId("math-draft-preview")).toBeNull();
  });

  it("BUG FIX regression: sent $-delimited math still uses draft preview", async () => {
    const { getByTestId } = await render(
      <UserMessageContent message={userMessage("$x^2 = 4$")} />,
    );
    expect(getByTestId("math-draft-preview")).toBeOnTheScreen();
  });
});

describe("UserMessageContent quiz-answer chip", () => {
  it("renders a lone letter as a normal bubble when it is not a quiz reply", async () => {
    const { getByText, queryByLabelText } = await render(
      <UserMessageContent message={userMessage("c")} />,
    );
    expect(getByText("c")).toBeOnTheScreen();
    expect(queryByLabelText("Quiz answer C")).toBeNull();
  });

  it("renders the quiz chip only when isQuizReply is set", async () => {
    const { getByLabelText, queryByText } = await render(
      <UserMessageContent message={userMessage("c")} isQuizReply />,
    );
    expect(getByLabelText("Quiz answer C")).toBeOnTheScreen();
    expect(queryByText("c")).toBeNull();
  });
});
