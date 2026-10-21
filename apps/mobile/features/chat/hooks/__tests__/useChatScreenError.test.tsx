import { act, renderHook } from "@testing-library/react-native";
import {
  useChatErrorHandlers,
  useChatErrorRecovery,
  useChatStreamLifecycle,
} from "@/features/chat/hooks/useChatScreenError";
import { useQuotaNudge } from "@/features/chat/hooks/useQuotaNudge";

jest.mock("react-i18next", () => {
  const t = (key: string) => key;
  return { useTranslation: () => ({ t }) };
});
jest.mock("@/features/chat/hooks/useQuotaNudge", () => ({ useQuotaNudge: jest.fn() }));
let mockProfileValidated = false;
jest.mock("@/contexts/AuthContext", () => ({
  useAuthOptional: () => ({ profileValidated: mockProfileValidated }),
}));

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

it("tells the quota nudge whether the plan came from the server yet", async () => {
  mockProfileValidated = false;
  const props = { streamActive: false, dismissChatError: jest.fn(), token: "tok", isPaid: false };
  const { rerender } = await renderHook(() => useChatStreamLifecycle(props));
  expect(useQuotaNudge).toHaveBeenLastCalledWith({ token: "tok", isPaid: false, planKnown: false, refreshKey: 0 });

  mockProfileValidated = true;
  await rerender({});
  expect(useQuotaNudge).toHaveBeenLastCalledWith({ token: "tok", isPaid: false, planKnown: true, refreshKey: 0 });
});
