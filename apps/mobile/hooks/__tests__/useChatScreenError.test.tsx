import { act, renderHook } from "@testing-library/react-native";
import { useChatErrorHandlers, useChatErrorRecovery } from "@/hooks/useChatScreenError";

jest.mock("react-i18next", () => {
  const t = (key: string) => key;
  return { useTranslation: () => ({ t }) };
});
jest.mock("@/hooks/useQuotaNudge", () => ({ useQuotaNudge: jest.fn() }));

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
