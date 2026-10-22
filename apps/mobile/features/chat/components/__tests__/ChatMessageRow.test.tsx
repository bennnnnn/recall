import { render } from "@testing-library/react-native";

import { ChatMessageRow } from "@/features/chat/components/ChatMessageRow";
import { StreamingChatMessageRow } from "@/features/chat/components/StreamingChatMessageRow";
import type { Message } from "@/lib/api";

jest.mock("@/features/chat/components/MessageBubble", () => {
  const { Text: MockText } =
    jest.requireActual("react-native") as typeof import("react-native");
  return {
    MessageBubble: ({ message }: { message: Message }) => {
      // Stand-in for any part of a bubble outside the markdown boundary
      // (images, places, proposal cards, sources) meeting data it can't draw.
      if (message.content === "bad") throw new Error("cannot draw this block");
      return <MockText>{message.content}</MockText>;
    },
  };
});
jest.mock("@/contexts/StreamingDraftContext", () => ({
  useStreamingDraft: () => null,
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

const message = (id: string, content: string): Message =>
  ({
    id,
    role: "assistant",
    content,
    model: "free-chat",
    created_at: "2026-01-01T00:00:00Z",
  }) as Message;

const rowProps = {
  priorUserText: null,
  streamVisualActive: false,
  lastAssistantId: null,
  selectedModel: "free-chat",
  highlightedMessageId: null,
  sendingMessageId: null,
  onRegenerate: jest.fn(),
  onFeedback: jest.fn(),
};

describe("chat rows contain a render error", () => {
  let consoleError: jest.SpyInstance;
  beforeEach(() => {
    // React logs every caught render error; the assertions below are the point.
    consoleError = jest.spyOn(console, "error").mockImplementation(() => {});
  });
  afterEach(() => {
    consoleError.mockRestore();
  });

  it("shows one quiet line for a reply that cannot be drawn and keeps the rest", async () => {
    const view = await render(
      <>
        <ChatMessageRow item={message("a", "fine before")} {...rowProps} />
        <ChatMessageRow item={message("b", "bad")} {...rowProps} />
        <ChatMessageRow item={message("c", "fine after")} {...rowProps} />
      </>,
    );
    expect(view.getByText("fine before")).toBeTruthy();
    expect(view.getByText("chat.message_render_failed")).toBeTruthy();
    expect(view.getByText("fine after")).toBeTruthy();
  });

  it("draws the next reply when the list reuses a failed row", async () => {
    const view = await render(<ChatMessageRow item={message("b", "bad")} {...rowProps} />);
    expect(view.getByText("chat.message_render_failed")).toBeTruthy();
    await view.rerender(<ChatMessageRow item={message("c", "recycled")} {...rowProps} />);
    expect(view.getByText("recycled")).toBeTruthy();
    expect(view.queryByText("chat.message_render_failed")).toBeNull();
  });

  it("contains a streaming reply that cannot be drawn", async () => {
    const view = await render(
      <StreamingChatMessageRow item={message("streaming", "bad")} {...rowProps} streamVisualActive />,
    );
    expect(view.getByText("chat.message_render_failed")).toBeTruthy();
  });
});
