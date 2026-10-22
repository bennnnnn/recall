import { useCallback, type RefObject } from "react";

import type { Message } from "@/lib/api";
import { clientGeoWsFields, type ClientGeo } from "@/lib/clientGeo";
import { headRejectedSend, type ChatTurnEvent, type ChatTurnState } from "@/features/chat/model/chatTurnCore";
import type { ComposerSendDraft, RejectedSend, SendMessageOptions } from "@/features/chat/model/sendLogic";
import type { useChatTransport } from "@/features/chat/hooks/useChatTransport";

type Options = {
  token: string | null;
  chatId: string | null;
  isCurrentView: () => boolean;
  /** The turn machine (useChat holds it) and one step of it. */
  turn: RefObject<ChatTurnState>;
  step: (event: ChatTurnEvent) => void;
  messagesRef: RefObject<Message[]>;
  transport: Pick<ReturnType<typeof useChatTransport>, "connect" | "sendViaSse" | "regenerateViaSse" | "currentSocket">;
  onUnreachable: () => void;
};

/**
 * What the user does to a turn: send, retry a rejected send, regenerate, stop. Each
 * steps the turn machine, then talks to the server over the socket or, when the socket
 * is not open, over SSE; an attempt the user has since replaced goes no further.
 */
export function useChatTurnActions({ token, chatId, isCurrentView, turn, step, messagesRef, transport, onUnreachable }: Options) {
  const { connect, sendViaSse, regenerateViaSse, currentSocket } = transport;

  const ensureConnected = useCallback(async () => {
    try {
      await connect();
    } catch {
      onUnreachable();
    }
  }, [connect, onUnreachable]);

  const dispatchSend = useCallback(async (content: string, options?: SendMessageOptions, retrying?: RejectedSend) => {
    if (!token || !chatId || !isCurrentView() || turn.current.phase !== "idle") return;
    step({ type: "send", content, options, retrying });
    const { attempt, ttftTurnId } = turn.current;
    await ensureConnected();
    if (!isCurrentView() || turn.current.attempt !== attempt) return;
    step({ type: "send_dispatched", retrying });
    const sse = () => sendViaSse(content, {
      attachmentIds: options?.attachmentIds,
      model: options?.model,
      clientGeo: options?.clientGeo,
      ttftTurnId,
    });
    const socket = currentSocket();
    if (!socket?.isOpen() || socket.shouldUseSse()) {
      await sse();
      return;
    }
    step({ type: "fallback_armed", fallback: { transport: socket, retry: sse } });
    socket.sendMessage({
      content,
      attachment_ids: options?.attachmentIds ?? [],
      model: options?.model ?? null,
      ...clientGeoWsFields(options?.clientGeo),
    });
  }, [token, chatId, isCurrentView, turn, step, ensureConnected, sendViaSse, currentSocket]);

  const sendMessage = useCallback(
    (content: string, options?: SendMessageOptions) => dispatchSend(content, options),
    [dispatchSend],
  );

  const retryRejectedSend = useCallback(async (): Promise<boolean> => {
    if (!token || !chatId || !isCurrentView() || turn.current.phase !== "idle") return false;
    const rejected = headRejectedSend(turn.current);
    if (!rejected || rejected.reason !== "send_rejected") return false;
    const attempt = turn.current.attempt + 1;
    await dispatchSend(rejected.content, rejected.options, rejected);
    return isCurrentView() && turn.current.attempt === attempt;
  }, [token, chatId, isCurrentView, turn, dispatchSend]);

  const restoreRejectedAttachmentDraft = useCallback((restore: (draft: ComposerSendDraft) => boolean): boolean => {
    if (!token || !chatId || !isCurrentView() || turn.current.phase !== "idle") return false;
    const rejected = headRejectedSend(turn.current);
    if (!rejected || rejected.reason !== "attachment_rejected") return false;
    const original = rejected.options.composerDraft ?? { text: rejected.content, attachment: null };
    const attachment = original.attachment ? { ...original.attachment } : null;
    // The server rejected this reference: a local file uploads again on send, or is replaced.
    if (attachment) delete attachment.existingAttachmentId;
    if (!restore({ text: original.text, attachment })) return false;
    step({ type: "rejected_draft_restored" });
    return true;
  }, [token, chatId, isCurrentView, turn, step]);

  const beginRegenerateUi = useCallback(() => {
    if (!isCurrentView()) return;
    step({ type: "regenerate_ui", messages: messagesRef.current });
    const { attempt } = turn.current;
    return () => isCurrentView() && turn.current.attempt === attempt;
  }, [isCurrentView, step, messagesRef, turn]);

  const cancelRegenerateUi = useCallback(() => {
    if (isCurrentView()) step({ type: "regenerate_cancelled" });
  }, [isCurrentView, step]);

  const regenerateResponse = useCallback(async (model?: string | null, clientGeo?: ClientGeo | null) => {
    if (!token || !chatId || !isCurrentView()) return;
    step({ type: "regenerate", messages: messagesRef.current });
    const { attempt } = turn.current;
    await ensureConnected();
    if (!isCurrentView() || turn.current.attempt !== attempt) return;
    const socket = currentSocket();
    if (!socket?.isOpen() || socket.shouldUseSse()) {
      await regenerateViaSse(model, clientGeo);
      return;
    }
    step({ type: "fallback_armed", fallback: { transport: socket, retry: () => regenerateViaSse(model, clientGeo) } });
    socket.sendRegenerate({ model: model ?? null, ...clientGeoWsFields(clientGeo) });
  }, [token, chatId, isCurrentView, step, messagesRef, turn, ensureConnected, regenerateViaSse, currentSocket]);

  const stopGeneration = useCallback(() => {
    if (isCurrentView()) step({ type: "stop" });
  }, [isCurrentView, step]);

  return {
    sendMessage,
    retryRejectedSend,
    restoreRejectedAttachmentDraft,
    beginRegenerateUi,
    cancelRegenerateUi,
    regenerateResponse,
    stopGeneration,
  };
}
