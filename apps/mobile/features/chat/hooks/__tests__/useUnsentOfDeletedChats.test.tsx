// Review of #2621: a message typed into a chat deleted on the laptop was refused (not found),
// kept under Retry on that chat, and lost once the screen moved to New chat.
import { act, renderHook } from "@testing-library/react-native";

import { useUnsentOfDeletedChats } from "@/features/chat/hooks/useUnsentOfDeletedChats";
import { headRejectedSend, initialChatTurnState, type ChatTurnEvent, type ChatTurnState } from "@/features/chat/model/chatTurnCore";
import { reduceChatTurn } from "@/features/chat/model/chatTurnState";
import type { RejectedSend } from "@/features/chat/model/sendLogic";
import {
  resetComposerAttachmentQueueForTest,
  takeQueuedComposerAttachment,
} from "@/features/attachments/model/pendingComposerAttachment";
import type { PendingAttachment } from "@/features/attachments/model/attachments";
import { emitAppEvent } from "@/lib/appEvents";

jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 1 }));
const mockComposer = { stashFailedDraftForThread: jest.fn() };
jest.mock("@/features/chat/context/ComposerDraftContext", () => ({
  useComposerDraftApiOptional: () => mockComposer,
}));

const picked = { localUri: "file://photo.jpg", fileName: "photo.jpg", kind: "image", contentType: "image/jpeg" } as PendingAttachment;

function rejected(text: string, attachment: PendingAttachment | null = null): RejectedSend {
  return {
    content: text,
    options: { composerDraft: { text, attachment } },
    messageId: `local-${text}`,
    retryingRejected: false,
    dispatched: true,
    reason: "send_rejected",
  } as RejectedSend;
}

function harness(rejectedByChat: Record<string, RejectedSend[]>) {
  const turn: { current: ChatTurnState } = { current: initialChatTurnState("gone", 1) };
  turn.current = { ...turn.current, rejected: new Map(Object.entries(rejectedByChat)) };
  const step = jest.fn((event: ChatTurnEvent) => {
    turn.current = reduceChatTurn(turn.current, event, 0).state;
  });
  return { turn, step };
}

beforeEach(() => {
  jest.clearAllMocks();
  resetComposerAttachmentQueueForTest();
});

it("gives a deleted chat's unsent messages to New chat's composer, text and file, and drops them from the chat", async () => {
  const { turn, step } = harness({ gone: [rejected("A long message", picked)], other: [rejected("Keep me")] });
  await renderHook(() => useUnsentOfDeletedChats(turn, step));

  await act(async () => {
    emitAppEvent("chatsDeleted", { chatIds: ["gone"] });
    await Promise.resolve();
  });

  expect(mockComposer.stashFailedDraftForThread).toHaveBeenCalledWith("new", "A long message");
  expect(takeQueuedComposerAttachment("new")).toBe(picked);
  expect(turn.current.rejected.get("gone") ?? []).toEqual([]);
  expect(headRejectedSend({ ...turn.current, chatId: "other" })?.content).toBe("Keep me");
});

it("does nothing for a deleted chat with nothing unsent", async () => {
  const { turn, step } = harness({});
  await renderHook(() => useUnsentOfDeletedChats(turn, step));
  await act(async () => { emitAppEvent("chatsDeleted", { chatIds: ["gone"] }); });
  expect(step).not.toHaveBeenCalled();
  expect(mockComposer.stashFailedDraftForThread).not.toHaveBeenCalled();
});
