import React from "react";
import * as Clipboard from "expo-clipboard";
import { act, fireEvent, render } from "@testing-library/react-native";

import { MessageBubble } from "@/features/chat/components/MessageBubble";
import { readReplyAloud, stopReadingAloud } from "@/features/speech/model/pronunciation";
import { endReadAloud } from "@/features/speech/model/readAloudSession";
import type { Message } from "@/lib/api";
import { selection, tap } from "@/lib/haptics";

let mockShowLiveClock = false;
let mockMarkdownPresented = false;
let mockHasContent = true;

jest.mock("@/ui/icons/Icon", () => {
  const { Text: MockText } =
    jest.requireActual("react-native") as typeof import("react-native");
  return {
    Icon: ({ name, color }: { name: string; color?: string }) => (
      <MockText testID={`icon-${name}`} accessibilityHint={color}>{name}</MockText>
    ),
  };
});
jest.mock("@/features/chat/components/UserMessageContent", () => {
  const { Text: MockText } =
    jest.requireActual("react-native") as typeof import("react-native");
  return {
    UserMessageContent: ({ message, actionsHint }: { message: Message; actionsHint?: string }) => (
      <MockText accessibilityHint={actionsHint}>{message.content}</MockText>
    ),
  };
});
jest.mock("@/components/MarkdownContent", () => {
  const { Text: MockText } =
    jest.requireActual("react-native") as typeof import("react-native");
  return {
    MarkdownContent: ({ content, presented }: { content: string; presented?: boolean }) => (
      <MockText testID={presented ? "markdown-presented" : "markdown"}>{content}</MockText>
    ),
  };
});
jest.mock("@/features/chat/components/SettingsProposalCard", () => ({
  SettingsProposalCard: () => null,
}));
jest.mock("@/features/todos/components/ReminderProposalCard", () => ({
  ReminderProposalCard: () => null,
}));
jest.mock("@/components/rich/PlacesListBlock", () => ({
  PlacesListBlock: () => null,
}));
jest.mock("@/features/attachments/components/ChatMessageImageStrip", () => ({
  ChatMessageImageStrip: () => null,
}));
jest.mock("@/features/images/components/ImageGenPlaceholder", () => {
  const { View: MockView } = jest.requireActual("react-native") as typeof import("react-native");
  return { ImageGenPlaceholder: () => <MockView testID="image-gen-placeholder" /> };
});
jest.mock("@/ui/feedback/ActionShimmer", () => ({
  ActionShimmer: () => null,
}));
jest.mock("@/features/chat/components/SearchSourcesStack", () => ({
  SearchSourcesStack: () => null,
}));
jest.mock("@/components/rich/LazyHeavyRich", () => ({
  LazyCircularClockBlock: ({ content }: { content: string }) => {
    const { Text: MockText } =
      jest.requireActual("react-native") as typeof import("react-native");
    return <MockText testID="lazy-message-clock">{content}</MockText>;
  },
}));
jest.mock("@/features/chat/components/MarkdownErrorBoundary", () => ({
  MarkdownErrorBoundary: ({ children }: { children: React.ReactNode }) =>
    children,
}));
jest.mock("@/features/chat/components/RecallTypingIndicator", () => {
  const { View: MockView } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    RecallTypingIndicator: ({ phase }: { phase?: string }) => (
      <MockView testID={`typing-indicator-${phase ?? "none"}`} />
    ),
  };
});
jest.mock("@/features/chat/components/StreamProgressLabel", () => {
  const { Text: MockText } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    StreamProgressLabel: ({ phase, startedAt }: { phase: string; startedAt?: number }) => (
      <MockText testID={`progress-${phase}`}>{String(startedAt)}</MockText>
    ),
  };
});
jest.mock("@/features/drafts/context/emailDraftPersist", () => ({
  AssistantMessageScope: ({ children }: { children: React.ReactNode }) => children,
}));
let mockAuthUser: { plan: string; features: string[]; locale: string; tts_voice?: string } | null = null;
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ user: mockAuthUser }),
  useAuthUserReader: () => () => mockAuthUser,
  useAuthToken: () => "token",
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => null,
}));
jest.mock("@/features/chat/hooks/useAssistantMessageContent", () => ({
  useAssistantMessageContent: ({ isUser }: { isUser: boolean }) => ({
    hasContent: mockHasContent,
    showActionSlot: !isUser,
    actionsReady: !isUser,
    showLiveClock: mockShowLiveClock,
    clockTimezone: "America/New_York",
    settingsProposals: [],
    showSettingsProposals: false,
    reminderProposals: [],
    showReminderProposals: false,
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
    markdownPresented: mockMarkdownPresented,
  }),
}));
jest.mock("@/lib/haptics", () => ({
  notifySuccess: jest.fn(),
  notifyWarning: jest.fn(),
  selection: jest.fn(),
  tap: jest.fn(),
}));
// As the real one does, a reading holds the read-aloud session (the row's icon reads it).
let mockReading: Promise<{ ok: true }> = Promise.resolve({ ok: true });
jest.mock("@/features/speech/model/pronunciation", () => {
  const session = jest.requireActual("@/features/speech/model/readAloudSession");
  return {
    readAloudIsCut: jest.fn(() => false),
    readReplyAloud: jest.fn(async (messageId: string) => {
      const id = session.startReadAloud(messageId);
      const result = await mockReading;
      session.endReadAloud(id);
      return result;
    }),
    stopReadingAloud: jest.fn(() => session.endReadAloud()),
  };
});
// A test that leaves a reading going would show the next test's row as reading.
afterEach(async () => {
  mockReading = Promise.resolve({ ok: true });
  await act(async () => endReadAloud());
});
jest.mock("@/lib/theme", () => ({
  useTheme: () => ({
    primary: "#36f",
    textSecondary: "#666",
    danger: "#f00",
    success: "#0a0",
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

describe("MessageBubble tool status (S7.9)", () => {
  afterEach(() => {
    mockHasContent = true;
  });

  it("draws the image-generation card only for image generation, not a photo lookup", async () => {
    mockHasContent = false;
    const waiting = { ...assistantMessage, id: "streaming", content: "" } as Message;
    const photo = await render(
      <MessageBubble message={waiting} isGenerating streamStatus="finding_photo" />,
    );
    expect(photo.queryByTestId("image-gen-placeholder")).toBeNull();
    expect(photo.getByTestId("typing-indicator-finding_photo")).toBeTruthy();
    await photo.unmount();

    const generating = await render(
      <MessageBubble message={waiting} isGenerating streamStatus="image_gen" />,
    );
    expect(generating.getByTestId("image-gen-placeholder")).toBeTruthy();
  });

  it("counts thinking from its start under the typing indicator", async () => {
    mockHasContent = false;
    const waiting = { ...assistantMessage, id: "streaming", content: "" } as Message;
    const view = await render(
      <MessageBubble
        message={waiting}
        isGenerating
        streamStatus="thinking"
        streamStatusStartedAt={1234}
      />,
    );
    expect(view.getByTestId("typing-indicator-thinking")).toBeTruthy();
    expect(view.getByTestId("progress-thinking").props.children).toBe("1234");
    // Not the old rotating label: thinking has its own timed one.
    expect(view.queryByText("chat.status.thinking")).toBeNull();
  });

  it("says the answer is being checked under a reply that has streamed", async () => {
    mockHasContent = true;
    const streamed = { ...assistantMessage, id: "streaming" } as Message;
    const view = await render(
      <MessageBubble
        message={streamed}
        isGenerating
        liveContent="x = 4"
        streamStatus="checking"
        streamStatusStartedAt={99}
      />,
    );
    expect(view.queryByTestId("typing-indicator-checking")).toBeNull();
    expect(view.getByTestId("progress-checking").props.children).toBe("99");
  });

  it("shows no progress once the reply has settled", async () => {
    mockHasContent = true;
    const view = await render(
      <MessageBubble message={assistantMessage} streamStatus="checking" />,
    );
    expect(view.queryByTestId("progress-checking")).toBeNull();
  });
});

describe("MessageBubble copy feedback timers", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockShowLiveClock = false;
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("leaves a sent message's photo, file and link buttons reachable by a screen reader", async () => {
    // iOS reads an accessible view as one element: a button inside it is never reached.
    const view = await render(<MessageBubble message={userMessage} />);
    const wrappers: string[] = [];
    for (let node = view.getByText("User message").parent; node; node = node.parent) {
      if (node.props.accessible === true) wrappers.push(String(node.props.testID ?? node.type));
    }
    expect(wrappers).toEqual([]);
    expect(view.getByA11yHint("chat.user_message_actions_hint")).toBeTruthy();
  });

  it("opens a sent message's actions with the long-press tap every menu uses", async () => {
    const view = await render(<MessageBubble message={userMessage} />);
    await fireEvent(view.getByA11yHint("chat.user_message_actions_hint"), "longPress");
    expect(view.getByLabelText("common.copy")).toBeTruthy();
    expect(tap).toHaveBeenCalledTimes(1);
    expect(selection).not.toHaveBeenCalled();
  });

  it("cleans up the user copy reset timer on unmount", async () => {
    const clearSpy = jest.spyOn(globalThis, "clearTimeout");
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
    expect(view.getByTestId("icon-check")).toBeTruthy();

    await act(async () => {
      view.unmount();
    });
    expect(clearSpy).toHaveBeenCalled();
    clearSpy.mockRestore();
  });

  it("cleans up the assistant copy reset timer on unmount", async () => {
    const clearSpy = jest.spyOn(globalThis, "clearTimeout");
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
    expect(view.getByTestId("icon-check")).toBeTruthy();

    await act(async () => {
      view.unmount();
    });
    expect(clearSpy).toHaveBeenCalled();
    clearSpy.mockRestore();
  });

  it.each([
    ["up", "icon-thumbs-up", "#0a0"],
    ["down", "icon-thumbs-down", "#f00"],
  ] as const)("fills a %s rating green for good, red for bad", async (feedback, icon, color) => {
    const view = await render(<MessageBubble message={{ ...assistantMessage, feedback } as Message} />);
    expect(view.getByTestId(icon).props.accessibilityHint).toBe(color);
  });

  it("tells a screen reader which rating is on and that a reply is being read", async () => {
    const rated = { ...assistantMessage, feedback: "up" } as Message;
    const view = await render(<MessageBubble message={rated} />);
    expect(view.getByLabelText("chat.thumbs_up_a11y").props.accessibilityState).toMatchObject({ selected: true });
    expect(view.getByLabelText("chat.thumbs_down_a11y").props.accessibilityState).toMatchObject({ selected: false });

    mockReading = new Promise(() => {});
    expect(view.getByLabelText("chat.read_aloud_a11y").props.accessibilityState).toMatchObject({ selected: false });
    await fireEvent.press(view.getByLabelText("chat.read_aloud_a11y"));
    expect(view.getByLabelText("chat.read_aloud_a11y").props.accessibilityState).toMatchObject({ selected: true });
  });

  describe("read aloud", () => {
    afterEach(() => {
      mockAuthUser = null;
    });

    it("reads with the phone's own voice when the plan has no read-aloud", async () => {
      mockAuthUser = { plan: "free", features: ["image_generation"], locale: "en" };
      const view = await render(<MessageBubble message={assistantMessage} />);
      await fireEvent.press(view.getByLabelText("chat.read_aloud_a11y"));
      const options = jest.mocked(readReplyAloud).mock.calls.at(-1)?.[3];
      expect(options).toEqual({ token: null, preferCloud: false, voice: null });
    });

    it("uses the natural voice on a plan that includes read-aloud", async () => {
      mockAuthUser = {
        plan: "plus",
        features: ["all_models", "image_generation", "speech_transcription", "speech_tts"],
        locale: "en",
        tts_voice: "cedar",
      };
      const view = await render(<MessageBubble message={assistantMessage} />);
      await fireEvent.press(view.getByLabelText("chat.read_aloud_a11y"));
      const options = jest.mocked(readReplyAloud).mock.calls.at(-1)?.[3];
      // The voice keys the clips kept for a reply: a voice changed since is asked for anew.
      expect(options).toEqual({ token: "token", preferCloud: true, voice: "cedar" });
    });

    it("keeps reading when the reply leaves the screen; the player over the composer stops it", async () => {
      mockReading = new Promise(() => {});
      const view = await render(<MessageBubble message={assistantMessage} />);
      await fireEvent.press(view.getByLabelText("chat.read_aloud_a11y"));
      expect(readReplyAloud).toHaveBeenCalledTimes(1);
      await act(async () => {
        view.unmount();
      });
      expect(stopReadingAloud).not.toHaveBeenCalled();
    });

    it("shows a reused row the state of its own reply", async () => {
      mockReading = new Promise(() => {});
      const view = await render(<MessageBubble message={assistantMessage} />);
      await fireEvent.press(view.getByLabelText("chat.read_aloud_a11y"));
      await view.rerender(
        <MessageBubble message={{ ...assistantMessage, id: "assistant-2" }} />,
      );
      // The reused row is not the Stop of the reply it showed before: it starts its own.
      expect(view.getByLabelText("chat.read_aloud_a11y").props.accessibilityState).toMatchObject({
        selected: false,
      });
      await fireEvent.press(view.getByLabelText("chat.read_aloud_a11y"));
      expect(jest.mocked(readReplyAloud).mock.calls.at(-1)?.[0]).toBe("assistant-2");
      expect(stopReadingAloud).not.toHaveBeenCalled();
    });

    it("stops its own reading when pressed again", async () => {
      mockReading = new Promise(() => {});
      const view = await render(<MessageBubble message={assistantMessage} />);
      await fireEvent.press(view.getByLabelText("chat.read_aloud_a11y"));
      await fireEvent.press(view.getByLabelText("chat.read_aloud_a11y"));
      expect(stopReadingAloud).toHaveBeenCalledTimes(1);
      expect(view.getByLabelText("chat.read_aloud_a11y").props.accessibilityState).toMatchObject({
        selected: false,
      });
    });
  });

  it("dispatches live clocks through the lazy rich boundary", async () => {
    mockShowLiveClock = true;
    const view = await render(<MessageBubble message={assistantMessage} />);
    expect(view.getByTestId("lazy-message-clock")).toHaveTextContent(
      "America/New_York",
    );
  });
});

describe("MessageBubble markdown presentation", () => {
  afterEach(() => {
    mockMarkdownPresented = false;
  });

  it("hands a reply the server presented to the renderer as presented", async () => {
    mockMarkdownPresented = true;
    const view = await render(<MessageBubble message={assistantMessage} />);
    expect(view.getByTestId("markdown-presented")).toBeTruthy();
  });

  it("leaves other replies for the phone to present", async () => {
    const view = await render(<MessageBubble message={assistantMessage} />);
    expect(view.getByTestId("markdown")).toBeTruthy();
  });
});

describe("MessageBubble footer under a cut-short reply", () => {
  it.each([
    [{ generationStopped: true }, "chat.generation_stopped"],
    // Saved with the reply, so a reopened chat still says it was stopped.
    [{ completion: "user_stop" as const }, "chat.generation_stopped"],
    [{ completion: "interrupted" as const }, "chat.generation_stopped"],
    [{ replyNotSaved: true }, "chat.reply_not_saved"],
  ])("says what happened to a reply marked %o", async (mark, label) => {
    const view = await render(<MessageBubble message={{ ...assistantMessage, ...mark }} />);
    expect(view.getByText(label)).toBeTruthy();
  });

  it("says nothing under a whole, saved reply", async () => {
    const view = await render(<MessageBubble message={assistantMessage} />);
    expect(view.queryByText("chat.generation_stopped")).toBeNull();
    expect(view.queryByText("chat.reply_not_saved")).toBeNull();
  });
});
