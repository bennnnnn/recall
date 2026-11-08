import { useCallback } from "react";

import { api } from "@/lib/api";
import { isServerMessageId } from "@/lib/serverMessageId";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { reportFailure } from "@/lib/sentry";
import type { EditThread } from "@/features/chat/model/threadEdit";

type Options = {
  token: string | null;
  chatId: string | null;
  editThread: EditThread;
  t: (key: string) => string;
};

/** A thumb up or down on a reply: shown at once, saved, and taken back with a word when it cannot be. */
export function useMessageFeedback({ token, chatId, editThread, t }: Options) {
  const feedback = useActionFeedbackOptional();
  return useCallback(
    (messageId: string, next: "up" | "down" | null) => {
      // A reply the server has not saved yet (one stopped before its id came) cannot keep a
      // rating: the thumb filled and the rating never left the phone. It stays as it was, and says so.
      if (!token || !chatId || !isServerMessageId(messageId)) {
        reportRecoverableError(feedback, t("chat.feedback_failed"));
        return;
      }
      let previous: "up" | "down" | null = null;
      editThread(
        (prev) =>
          prev.map((mm) => {
            if (mm.id !== messageId) return mm;
            previous = mm.feedback ?? null;
            return { ...mm, feedback: next };
          }),
        "feedback",
      );
      void api.setMessageFeedback(token, chatId, messageId, next).catch((error: unknown) => {
        // Only this tap goes back: a newer tap on the same reply keeps its rating.
        editThread(
          (prev) => prev.map((mm) =>
            mm.id === messageId && (mm.feedback ?? null) === next ? { ...mm, feedback: previous } : mm),
          "feedback",
        );
        reportRecoverableError(feedback, t("chat.feedback_failed"));
        reportFailure("message_feedback", error);
      });
    },
    [token, chatId, editThread, feedback, t],
  );
}
