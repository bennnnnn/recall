import { act, render } from "@testing-library/react-native";

import { StreamingChatMessageRow } from "@/features/chat/components/StreamingChatMessageRow";
import type { Message } from "@/lib/api";

let mockBubbleProps: { onRegenerate?: () => void } = {};

jest.mock("@/components/MessageBubble", () => ({
  MessageBubble: (props: { onRegenerate?: () => void }) => {
    mockBubbleProps = props;
    return null;
  },
}));
let mockDraft: { content: string } | null = null;
jest.mock("@/contexts/StreamingDraftContext", () => ({
  useStreamingDraft: () => mockDraft,
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/lib/theme", () => ({ useTheme: () => ({ textSecondary: "#666" }) }));

const item = {
  id: "assistant-1",
  role: "assistant",
  content: "Reply",
  model: "free-chat",
  created_at: "2026-01-01T00:00:00Z",
} as Message;

describe("StreamingChatMessageRow", () => {
  it("keeps the prebound regenerate callback stable across renders", async () => {
    const onRegenerate = jest.fn();
    const baseProps = {
      item,
      priorUserText: "Question",
      streamVisualActive: false,
      lastAssistantId: item.id,
      selectedModel: "free-chat",
      sendingMessageId: null,
      onRegenerate,
      onFeedback: jest.fn(),
    };
    const view = await render(
      <StreamingChatMessageRow
        {...baseProps}
        highlightedMessageId={null}
      />,
    );
    const first = mockBubbleProps.onRegenerate;

    await view.rerender(
      <StreamingChatMessageRow
        {...baseProps}
        highlightedMessageId="other"
      />,
    );

    expect(mockBubbleProps.onRegenerate).toBe(first);
    first?.();
    expect(onRegenerate).toHaveBeenCalledWith("free-chat");
  });
});

describe("StreamingChatMessageRow stall hint (S7.2)", () => {
  const streamingItem = { ...item, id: "streaming", content: "" } as Message;
  const props = {
    item: streamingItem,
    priorUserText: "Question",
    streamVisualActive: true,
    lastAssistantId: null,
    selectedModel: "free-chat",
    highlightedMessageId: null,
    sendingMessageId: null,
    onRegenerate: jest.fn(),
    onFeedback: jest.fn(),
  };

  beforeEach(() => {
    jest.useFakeTimers();
  });
  afterEach(() => {
    mockDraft = null;
    jest.useRealTimers();
  });

  it("says it is still working, and that Stop ends it, once text stops arriving for 20 s", async () => {
    mockDraft = { content: "The first part of the answer" };
    const view = await render(<StreamingChatMessageRow {...props} />);
    await act(async () => { jest.advanceTimersByTime(19_000); });
    expect(view.queryByTestId("stream-silence-hint")).toBeNull();
    await act(async () => { jest.advanceTimersByTime(1_500); });
    expect(view.getByText("chat.still_working")).toBeTruthy();

    // A new token clears it and restarts the wait.
    mockDraft = { content: "The first part of the answer, then more" };
    await view.rerender(<StreamingChatMessageRow {...props} item={{ ...streamingItem }} />);
    expect(view.queryByTestId("stream-silence-hint")).toBeNull();
  });

  it("says nothing before the first token or once the reply has ended", async () => {
    mockDraft = { content: "" };
    const waiting = await render(<StreamingChatMessageRow {...props} />);
    await act(async () => { jest.advanceTimersByTime(60_000); });
    expect(waiting.queryByTestId("stream-silence-hint")).toBeNull();
    await waiting.unmount();

    mockDraft = { content: "Done." };
    const ended = await render(<StreamingChatMessageRow {...props} streamVisualActive={false} />);
    await act(async () => { jest.advanceTimersByTime(60_000); });
    expect(ended.queryByTestId("stream-silence-hint")).toBeNull();
  });
});
