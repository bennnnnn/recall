import { act, renderHook } from "@testing-library/react-native";
import { useChatErrorHandlers } from "@/hooks/useChatScreenError";

jest.mock("react-i18next", () => {
  const t = (key: string) => key;
  return { useTranslation: () => ({ t }) };
});
jest.mock("@/hooks/useQuotaNudge", () => ({ useQuotaNudge: jest.fn() }));

it("clears the previous chat's rejection while preserving unrelated errors", async () => {
  const { result } = await renderHook(() => useChatErrorHandlers(false));
  await act(async () => { result.current.handleRejectedSendChange(true); });
  expect(result.current.chatError?.kind).toBe("send_rejected");

  await act(async () => { result.current.handleRejectedSendChange(false); });
  expect(result.current.chatError).toBeNull();
  await act(async () => { result.current.handleChatError("Connection lost"); });
  await act(async () => { result.current.handleRejectedSendChange(false); });
  expect(result.current.chatError).toEqual({ kind: "generic", message: "Connection lost" });

  // Returning to the original chat reveals its retained send again.
  await act(async () => { result.current.handleRejectedSendChange(true); });
  expect(result.current.chatError?.kind).toBe("send_rejected");
  const synchronize = result.current.handleRejectedSendChange;
  await act(async () => { result.current.dismissChatError(); });
  expect(result.current.chatError).toBeNull();
  // Dismissal does not change the callback and retrigger the screen effect.
  expect(result.current.handleRejectedSendChange).toBe(synchronize);
});
