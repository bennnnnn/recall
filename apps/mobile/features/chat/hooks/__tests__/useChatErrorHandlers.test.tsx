import { act, renderHook } from "@testing-library/react-native";
import {
  useChatErrorHandlers,
  useChatErrorRecovery,
  useChatStreamLifecycle,
} from "@/features/chat/hooks/useChatErrorHandlers";
import { abandonActiveChatIfDeleted } from "@/features/chat/drawer/drawer";
import { subscribeChatGone } from "@/features/chat/model/chatGone";
import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api/errorBody";

jest.mock("@/lib/api", () => ({ api: { getChat: jest.fn() } }));
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 0 }));
jest.mock("@/features/chat/drawer/drawer", () => ({ abandonActiveChatIfDeleted: jest.fn() }));

beforeEach(() => jest.clearAllMocks());

// Pre-launch review 2026-11-27: a send to a chat deleted on another device failed with the
// generic error, and the chat stayed open. The stream's not_found asks whether the chat is
// there (it may be only the message a regenerate answers that is gone).
describe("a turn refused as not found", () => {
  it("takes the open chat away when the chat itself is gone", async () => {
    (api.getChat as jest.Mock).mockRejectedValue(new ApiRequestError(404, JSON.stringify({ detail: "Chat not found" })));
    const told: string[] = [];
    const stop = subscribeChatGone((chatId) => void told.push(chatId));
    try {
      const { result } = await renderHook(() => useChatErrorHandlers(false, { token: "token", chatId: "gone-chat" }));
      await act(async () => { result.current.handleChatError("Chat not found.", "not_found"); });
      expect(api.getChat).toHaveBeenCalledWith("token", "gone-chat");
      expect(abandonActiveChatIfDeleted).toHaveBeenCalledWith(["gone-chat"]);
      expect(told).toEqual(["gone-chat"]);
    } finally {
      stop();
    }
  });

  it("asks for a send the server refused as not found, reported as the send's retry", async () => {
    (api.getChat as jest.Mock).mockRejectedValue(new ApiRequestError(404, JSON.stringify({ detail: "Chat not found" })));
    const { result } = await renderHook(() => useChatErrorHandlers(false, { token: "token", chatId: "gone-send" }));
    await act(async () => { result.current.handleChatError("Chat not found.", "send_rejected", "not_found"); });
    expect(abandonActiveChatIfDeleted).toHaveBeenCalledWith(["gone-send"]);
  });

  it("leaves a chat that is still there, and reads nothing for any other error", async () => {
    (api.getChat as jest.Mock).mockResolvedValue({ id: "here" });
    const { result } = await renderHook(() => useChatErrorHandlers(false, { token: "token", chatId: "here" }));
    await act(async () => { result.current.handleChatError("No user message to regenerate from.", "not_found"); });
    expect(abandonActiveChatIfDeleted).not.toHaveBeenCalled();
    (api.getChat as jest.Mock).mockClear();
    await act(async () => { result.current.handleChatError("Connection lost", "failed"); });
    expect(api.getChat).not.toHaveBeenCalled();
  });
});

it("clears the previous chat's rejection while preserving unrelated errors", async () => {
  const { result } = await renderHook(() => useChatErrorHandlers(false));
  await act(async () => { result.current.handleRejectedSendChange("send_rejected"); });
  expect(result.current.chatError?.kind).toBe("send_rejected");

  await act(async () => { result.current.handleRejectedSendChange(null); });
  expect(result.current.chatError).toBeNull();
  await act(async () => { result.current.handleChatError("Connection lost"); });
  await act(async () => { result.current.handleRejectedSendChange(null); });
  expect(result.current.chatError).toEqual({ kind: "generic", message: "Connection lost" });

  // Returning to the original chat reveals its retained send again.
  await act(async () => { result.current.handleRejectedSendChange("send_rejected"); });
  expect(result.current.chatError?.kind).toBe("send_rejected");
  const synchronize = result.current.handleRejectedSendChange;
  await act(async () => { result.current.dismissChatError(); });
  expect(result.current.chatError).toBeNull();
  // Dismissal does not change the callback and retrigger the screen effect.
  expect(result.current.handleRejectedSendChange).toBe(synchronize);
});

it("shows and clears the retained attachment rejection for the current conversation", async () => {
  const { result } = await renderHook(() => useChatErrorHandlers(false));
  await act(async () => { result.current.handleRejectedSendChange("attachment_rejected"); });
  expect(result.current.chatError).toEqual({ kind: "attachment_rejected", message: "chat.attachment_rejected" });
  await act(async () => { result.current.handleRejectedSendChange(null); });
  expect(result.current.chatError).toBeNull();
});

it.each([true, false])("only restores an unsaved attachment and never regenerates a saved reply (composer accepts: %s)", async (accept) => {
  const draft = { text: "unsaved", attachment: null };
  const restoreComposerDraft = jest.fn(() => accept);
  const restoreRejectedAttachmentDraft = jest.fn((restore) => restore(draft));
  const dismiss = jest.fn();
  const regenerate = jest.fn();
  const retryRejectedSend = jest.fn();
  const { result } = await renderHook(() => useChatErrorRecovery({
    error: { kind: "attachment_rejected", message: "unsaved" }, blocked: false,
    dismiss, regenerate, retryRejectedSend, restoreComposerDraft, restoreRejectedAttachmentDraft, selectedModel: "smart-chat",
  }));
  await act(async () => { result.current(); });
  expect(restoreComposerDraft).toHaveBeenCalledWith(draft);
  expect(dismiss).toHaveBeenCalledTimes(accept ? 1 : 0);
  expect(regenerate).not.toHaveBeenCalled();
  expect(retryRejectedSend).not.toHaveBeenCalled();
});

it("refuses all recovery actions while another send is active", async () => {
  const restore = jest.fn();
  const { result } = await renderHook(() => useChatErrorRecovery({
    error: { kind: "attachment_rejected", message: "unsaved" }, blocked: true,
    dismiss: jest.fn(), regenerate: jest.fn(), retryRejectedSend: jest.fn(),
    restoreComposerDraft: jest.fn(), restoreRejectedAttachmentDraft: restore, selectedModel: "smart-chat",
  }));
  await act(async () => { result.current(); });
  expect(restore).not.toHaveBeenCalled();
});

it("retries an unsaved send without regenerating", async () => {
  const retryRejectedSend = jest.fn();
  const regenerate = jest.fn();
  const dismiss = jest.fn();
  const { result } = await renderHook(() => useChatErrorRecovery({
    error: { kind: "send_rejected", message: "unsaved" }, blocked: false,
    dismiss, regenerate, retryRejectedSend, restoreComposerDraft: jest.fn(),
    restoreRejectedAttachmentDraft: jest.fn(), selectedModel: "smart-chat",
  }));
  await act(async () => { result.current(); });
  expect(retryRejectedSend).toHaveBeenCalledTimes(1);
  expect(regenerate).not.toHaveBeenCalled();
  expect(dismiss).toHaveBeenCalledTimes(1);
});

it("regenerates a saved reply without retrying an unsaved send", async () => {
  const retryRejectedSend = jest.fn();
  const regenerate = jest.fn();
  const { result } = await renderHook(() => useChatErrorRecovery({
    error: { kind: "generic", message: "Connection lost" }, blocked: false,
    dismiss: jest.fn(), regenerate, retryRejectedSend, restoreComposerDraft: jest.fn(),
    restoreRejectedAttachmentDraft: jest.fn(), selectedModel: "smart-chat",
  }));
  await act(async () => { result.current(); });
  expect(regenerate).toHaveBeenCalledWith("smart-chat");
  expect(retryRejectedSend).not.toHaveBeenCalled();
});

describe("the busy notice and its Stop", () => {
  function useScreenErrors({ streamActive, replySaving }: { streamActive: boolean; replySaving: boolean }) {
    const errors = useChatErrorHandlers(false);
    useChatStreamLifecycle({
      streamActive,
      replySaving,
      dismissChatError: errors.dismissChatError,
      dismissBusyNotice: errors.dismissBusyNotice,
    });
    return errors;
  }

  it("goes once the reply's text is all in, so Stop cannot cut its save short", async () => {
    const { result, rerender } = await renderHook(useScreenErrors, {
      initialProps: { streamActive: true, replySaving: false },
    });
    await act(async () => { result.current.handleStreamBusy(); });
    expect(result.current.chatError?.kind).toBe("busy");
    await rerender({ streamActive: true, replySaving: true });
    expect(result.current.chatError).toBeNull();
  });

  it("leaves any other error up while the reply saves", async () => {
    const { result, rerender } = await renderHook(useScreenErrors, {
      initialProps: { streamActive: true, replySaving: false },
    });
    await act(async () => { result.current.handleChatError("Connection lost"); });
    await rerender({ streamActive: true, replySaving: true });
    expect(result.current.chatError).toEqual({ kind: "generic", message: "Connection lost" });
  });
});
