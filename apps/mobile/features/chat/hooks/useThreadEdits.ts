import { useCallback, useEffect } from "react";

import { onAppEvent } from "@/lib/appEvents";
import type { ChatTurnCommand, ChatTurnEvent } from "@/features/chat/model/chatTurnCore";
import { withoutDeletedAttachment } from "@/features/chat/model/deletedAttachment";
import type { EditThread } from "@/features/chat/model/threadEdit";

type Options = {
  chatId: string | null;
  isCurrentView: () => boolean;
  /** One step of the chat's turn (useChat), which owns the thread; what it asked for. */
  step: (event: ChatTurnEvent) => readonly ChatTurnCommand[];
};

/**
 * The thread's other writers: each change to the list besides the turn's own frames is a
 * `thread_edit` step, so the turn reducer sequences every edit (structure ticket ST-08).
 */
export function useThreadEdits({ chatId, isCurrentView, step }: Options): EditThread {
  const editThread = useCallback<EditThread>(
    (update, source, belongsTo) =>
      step({ type: "thread_edit", source, update, chatId: belongsTo }).some((command) => command.type === "messages"),
    [step],
  );

  // A photo or file deleted from Library leaves the open chat as it left the server's copy.
  useEffect(() => onAppEvent("attachmentDeleted", ({ attachmentId, chatId: holder }) => {
    if (holder !== chatId || !isCurrentView()) return;
    editThread((previous) => withoutDeletedAttachment(previous, attachmentId), "attachment_deleted");
  }), [chatId, isCurrentView, editThread]);

  return editThread;
}
