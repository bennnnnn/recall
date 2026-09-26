import { render } from "@testing-library/react-native";

import { StreamingChatMessageRow } from "@/components/chat/StreamingChatMessageRow";
import type { Message } from "@/lib/api";

let mockBubbleProps: { onRegenerate?: () => void } = {};

jest.mock("@/components/MessageBubble", () => ({
  MessageBubble: (props: { onRegenerate?: () => void }) => {
    mockBubbleProps = props;
    return null;
  },
}));
jest.mock("@/contexts/StreamingDraftContext", () => ({
  useStreamingDraft: () => null,
}));

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
