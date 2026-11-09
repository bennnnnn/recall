import { useCallback, useRef } from "react";

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
  // Each reply's taps, counted: only the latest tap's failure takes its rating back.
  const taps = useRef(new Map<string, number>());
  return useCallback(
    (messageId: string, next: "up" | "down" | null) => {
      // A reply the server has not saved yet (one stopped before its id came) cannot keep a
      // rating: the thumb filled and the rating never left the phone. It stays as it was, and says so.
      if (!token || !chatId || !isServerMessageId(messageId)) {
        reportRecoverableError(feedback, t("chat.feedback_failed"));
        return;
      }
      const tap = (taps.current.get(messageId) ?? 0) + 1;
      taps.current.set(messageId, tap);
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
        reportFailure("message_feedback", error);
        // A newer tap on the same reply went out after this one: its rating stands, whatever it shows.
        if (taps.current.get(messageId) !== tap) return;
        editThread(
          (prev) => prev.map((mm) => (mm.id === messageId ? { ...mm, feedback: previous } : mm)),
          "feedback",
        );
        reportRecoverableError(feedback, t("chat.feedback_failed"));
      });
    },
    [token, chatId, editThread, feedback, t],
  );
}
