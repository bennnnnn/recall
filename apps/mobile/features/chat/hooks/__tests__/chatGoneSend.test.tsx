// Review of #2621: a send refused because its chat is gone, end to end. The stream's not_found
// frame reaches the error handlers as the send's `cause`, they read the chat, and a gone chat
// goes: the notice says so once and the unsent message waits in New chat's composer.
import React from "react";
import { act, cleanup, render } from "@testing-library/react-native";

import { ChatGoneNotice } from "@/features/chat/components/ChatGoneNotice";
import { useChat } from "@/features/chat/hooks/useChat";
import { useChatErrorHandlers } from "@/features/chat/hooks/useChatErrorHandlers";
import { ActionFeedbackContext, type ActionFeedbackApi } from "@/contexts/actionFeedbackCore";
import { ApiRequestError } from "@/lib/api/errorBody";

jest.mock("@/lib/api", () => ({
  chatWebSocketUrl: (id: string) => `wss://test/${id}`,
  api: { listMessages: jest.fn(), getChat: jest.fn(), stopChatStream: jest.fn(() => Promise.resolve()) },
}));
const getChat = jest.requireMock("@/lib/api").api.getChat as jest.Mock;
jest.mock("@/lib/deviceTimezone", () => ({ getDeviceTimezone: () => "UTC" }));
let mockIds = 0;
jest.mock("expo-crypto", () => ({ randomUUID: () => `name-${++mockIds}` }));
jest.mock("@react-native-community/netinfo", () => ({
  __esModule: true,
  default: { addEventListener: () => () => {} },
}));
jest.mock("expo-router", () => {
  const React = jest.requireActual("react");
  return {
    useFocusEffect: (effect: () => void | (() => void)) => React.useEffect(() => effect(), [effect]),
  };
});
jest.mock("@/features/chat/model/sse", () => ({
  streamChatMessageSse: jest.fn(),
  streamChatRegenerateSse: jest.fn(),
  shouldAbortPriorSse: (previous: string, next: string) => previous === next,
}));
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 0 }));
const mockAccountSession = { account: "user-1:0", getToken: () => "token" };
jest.mock("@/contexts/accountSession", () => ({ useAccountSession: () => mockAccountSession }));
const mockComposer = { stashFailedDraftForThread: jest.fn() };
jest.mock("@/features/chat/context/ComposerDraftContext", () => ({
  ...jest.requireActual("@/features/chat/context/ComposerDraftContext"),
  useComposerDraftApiOptional: () => mockComposer,
}));

class FakeSocket {
  static OPEN = 1;
  static instances: FakeSocket[] = [];
  readyState = 0;
  onopen = () => {};
  onclose = () => {};
  onerror = () => {};
  onmessage = (_event: { data: string }) => {};
  send = jest.fn();
  close = jest.fn(() => { this.readyState = 3; });
  constructor(readonly url: string) { FakeSocket.instances.push(this); }
  open() { this.readyState = FakeSocket.OPEN; this.onopen(); }
  emit(payload: object) { this.onmessage({ data: JSON.stringify(payload) }); }
}

const feedback = { info: jest.fn(), show: jest.fn(), success: jest.fn(), warning: jest.fn(), error: jest.fn(), dismiss: jest.fn() };
let current: ReturnType<typeof useChat>;

/** The chat screen's wiring (ChatScreen.tsx): the handlers know the open chat, and useChat reports to them. */
function Screen({ chatId }: { chatId: string }) {
  const errors = useChatErrorHandlers(false, { token: "token", chatId });
  const chat = useChat("token", chatId, { onError: errors.handleChatError });
  React.useLayoutEffect(() => { current = chat; });
  return null;
}

const originalSocket = globalThis.WebSocket;
beforeEach(() => {
  jest.clearAllMocks();
  FakeSocket.instances = [];
  globalThis.WebSocket = FakeSocket as unknown as typeof WebSocket;
});
afterEach(async () => {
  await cleanup();
  globalThis.WebSocket = originalSocket;
});

it("takes a chat found gone by a refused send away, says so once, and keeps the message for New chat", async () => {
  getChat.mockRejectedValue(new ApiRequestError(404, JSON.stringify({ detail: "Chat not found" })));
  await render(
    <ActionFeedbackContext.Provider value={feedback as unknown as ActionFeedbackApi}>
      <ChatGoneNotice />
      <Screen chatId="deleted-on-laptop" />
    </ActionFeedbackContext.Provider>,
  );
  await act(async () => {
    const pending = current.connect();
    FakeSocket.instances.at(-1)!.open();
    await pending;
  });
  const socket = FakeSocket.instances.at(-1)!;
  await act(async () => {
    await current.sendMessage("A long message typed before I knew");
    socket.emit({ type: "error", code: "not_found", message: "Chat not found.", user_message_saved: false });
    for (let i = 0; i < 10; i += 1) await Promise.resolve();
  });

  expect(getChat).toHaveBeenCalledWith("token", "deleted-on-laptop");
  expect(feedback.info).toHaveBeenCalledTimes(1);
  expect(feedback.info).toHaveBeenCalledWith("chat.gone_toast", expect.anything());
  expect(mockComposer.stashFailedDraftForThread).toHaveBeenCalledWith("new", "A long message typed before I knew");
  expect(current.rejectedSend).toBeNull();
});
