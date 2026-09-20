import React from "react";
import * as Clipboard from "expo-clipboard";
import { act, fireEvent, render } from "@testing-library/react-native";

import { MessageBubble } from "@/components/MessageBubble";
import type { Message } from "@/lib/api";

let mockShowLiveClock = false;

jest.mock("expo-clipboard", () => ({
  setStringAsync: jest.fn(async () => undefined),
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/components/Icon", () => {
  const { Text: MockText } =
    jest.requireActual("react-native") as typeof import("react-native");
  return {
    Icon: ({ name }: { name: string }) => (
      <MockText testID={`icon-${name}`}>{name}</MockText>
    ),
  };
});
jest.mock("@/components/UserMessageContent", () => {
  const { Text: MockText } =
    jest.requireActual("react-native") as typeof import("react-native");
  return {
    UserMessageContent: ({ message }: { message: Message }) => (
      <MockText>{message.content}</MockText>
    ),
  };
});
jest.mock("@/components/MarkdownContent", () => {
  const { Text: MockText } =
    jest.requireActual("react-native") as typeof import("react-native");
  return {
    MarkdownContent: ({ content }: { content: string }) => (
      <MockText>{content}</MockText>
    ),
  };
});
jest.mock("@/components/CalendarProposalCard", () => ({
  CalendarProposalCard: () => null,
}));
jest.mock("@/components/SettingsProposalCard", () => ({
  SettingsProposalCard: () => null,
}));
jest.mock("@/components/PlacesListBlock", () => ({
  PlacesListBlock: () => null,
}));
jest.mock("@/components/ChatMessageImageStrip", () => ({
  ChatMessageImageStrip: () => null,
}));
jest.mock("@/components/ImageGenPlaceholder", () => ({
  ImageGenPlaceholder: () => null,
}));
jest.mock("@/components/ActionShimmer", () => ({
  ActionShimmer: () => null,
}));
jest.mock("@/components/SearchSourcesStack", () => ({
  SearchSourcesStack: () => null,
}));
jest.mock("@/components/rich/LazyHeavyRich", () => ({
  LazyCircularClockBlock: ({ content }: { content: string }) => {
    const { Text: MockText } =
      jest.requireActual("react-native") as typeof import("react-native");
    return <MockText testID="lazy-message-clock">{content}</MockText>;
  },
}));
jest.mock("@/components/StreamingCursor", () => ({
  StreamingCursor: () => null,
}));
jest.mock("@/components/MarkdownErrorBoundary", () => ({
  MarkdownErrorBoundary: ({ children }: { children: React.ReactNode }) =>
    children,
}));
jest.mock("@/components/RecallTypingIndicator", () => ({
  RecallTypingIndicator: () => null,
}));
jest.mock("@/components/LearningLaunchButton", () => ({
  LearningLaunchButton: () => null,
}));
jest.mock("@/contexts/emailDraftPersist", () => ({
  AssistantMessageScope: ({ children }: { children: React.ReactNode }) => children,
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ user: null }),
  useAuthToken: () => "token",
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => null,
}));
jest.mock("@/hooks/useStreamLayoutHold", () => ({
  useStreamLayoutHold: () => false,
}));
jest.mock("@/hooks/useAssistantMessageContent", () => ({
  useAssistantMessageContent: ({ isUser }: { isUser: boolean }) => ({
    hasContent: true,
    showActionSlot: !isUser,
    actionsReady: !isUser,
    showLiveClock: mockShowLiveClock,
    clockTimezone: "America/New_York",
    calendarProposals: [],
    showCalendarProposals: false,
    settingsProposals: [],
    showSettingsProposals: false,
    places: [],
    showPlaces: false,
    images: [],
    showImages: false,
    markdownContent: isUser ? "" : "Assistant reply",
    hasMarkdown: !isUser,
    showSearchSources: false,
    searchSources: [],
    markdownStreamMode: false,
    markdownResetKey: "test",
    learningLaunch: null,
  }),
}));
jest.mock("@/lib/haptics", () => ({
  notifySuccess: jest.fn(),
  notifyWarning: jest.fn(),
  selection: jest.fn(),
  tap: jest.fn(),
}));
jest.mock("@/lib/speech/pronunciation", () => ({
  speakPlainText: jest.fn(async () => ({ ok: true })),
  stopSpeaking: jest.fn(),
}));
jest.mock("@/lib/theme", () => ({
  useTheme: () => ({
    primary: "#36f",
    textSecondary: "#666",
    danger: "#f00",
    textTertiary: "#777",
    primaryLight: "#eef",
  }),
}));

const userMessage = {
  id: "user-1",
  role: "user",
  content: "User message",
  model: null,
  created_at: "2026-01-01T00:00:00Z",
} as Message;

const assistantMessage = {
  id: "assistant-1",
  role: "assistant",
  content: "Assistant reply",
  model: "free-chat",
  created_at: "2026-01-01T00:00:00Z",
} as Message;

describe("MessageBubble copy feedback timers", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockShowLiveClock = false;
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("cleans up the user copy reset timer on unmount", async () => {
    const clearSpy = jest.spyOn(global, "clearTimeout");
    const view = await render(<MessageBubble message={userMessage} />);
    await fireEvent(
      view.getByA11yHint("chat.user_message_actions_hint"),
      "longPress",
    );

    await fireEvent.press(view.getByLabelText("common.copy"));
    await act(async () => {
      await Promise.resolve();
    });
    expect(Clipboard.setStringAsync).toHaveBeenCalledWith("User message");
    expect(view.getByTestId("icon-checkmark-outline")).toBeTruthy();

    await act(async () => {
      view.unmount();
    });
    expect(clearSpy).toHaveBeenCalled();
    clearSpy.mockRestore();
  });

  it("cleans up the assistant copy reset timer on unmount", async () => {
    const clearSpy = jest.spyOn(global, "clearTimeout");
    const view = await render(
      <MessageBubble
        message={assistantMessage}
        isLastAssistant
        onFeedback={jest.fn()}
      />,
    );

    await fireEvent.press(view.getByLabelText("common.copy"));
    await act(async () => {
      await Promise.resolve();
    });
    expect(Clipboard.setStringAsync).toHaveBeenCalledWith("Assistant reply");
    expect(view.getByTestId("icon-checkmark-outline")).toBeTruthy();

    await act(async () => {
      view.unmount();
    });
    expect(clearSpy).toHaveBeenCalled();
    clearSpy.mockRestore();
  });

  it("dispatches live clocks through the lazy rich boundary", async () => {
    mockShowLiveClock = true;
    const view = await render(<MessageBubble message={assistantMessage} />);
    expect(view.getByTestId("lazy-message-clock")).toHaveTextContent(
      "America/New_York",
    );
  });
});
