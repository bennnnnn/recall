import { useCallback, useEffect, useRef } from "react";

import { useAssistantMessageId, useEmailDraftSave } from "@/contexts/emailDraftPersist";
import { fullEmailText } from "@/lib/emailCompose";
import { registerEmailDraftFlusher } from "@/lib/emailDraftFlush";
import type { EmailDraft } from "@/lib/richBlocks";
import { isServerMessageId } from "@/lib/serverMessageId";

export const EMAIL_DRAFT_PERSIST_DEBOUNCE_MS = 600;

export function useEmailCardPersist(currentDraft: EmailDraft, editing: boolean) {
  const save = useEmailDraftSave();
  const messageId = useAssistantMessageId();
  const draftRef = useRef(currentDraft);
  draftRef.current = currentDraft;
  const lastSentRef = useRef(fullEmailText(currentDraft));
  const dirtyRef = useRef(false);
  const inFlightRef = useRef(0);

  const persistNow = useCallback(
    async (draft: EmailDraft) => {
      if (!save || !messageId || !isServerMessageId(messageId)) return;
      const text = fullEmailText(draft);
      if (text === lastSentRef.current) {
        dirtyRef.current = false;
        return;
      }
      inFlightRef.current += 1;
      dirtyRef.current = false;
      try {
        const ok = await save(messageId, draft);
        if (ok) lastSentRef.current = text;
        else dirtyRef.current = true;
      } finally {
        inFlightRef.current -= 1;
      }
    },
    [save, messageId],
  );

  useEffect(() => {
    if (editing || inFlightRef.current > 0) return;
    lastSentRef.current = fullEmailText(currentDraft);
    dirtyRef.current = false;
  }, [currentDraft.to, currentDraft.subject, currentDraft.body, editing]);

  useEffect(() => {
    if (!editing) return;
    dirtyRef.current = true;
    const timer = setTimeout(() => {
      void persistNow(draftRef.current);
    }, EMAIL_DRAFT_PERSIST_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [currentDraft.to, currentDraft.subject, currentDraft.body, editing, persistNow]);

  useEffect(
    () =>
      registerEmailDraftFlusher(async () => {
        if (!dirtyRef.current) return;
        await persistNow(draftRef.current);
      }),
    [persistNow],
  );

  useEffect(
    () => () => {
      if (dirtyRef.current) void persistNow(draftRef.current);
    },
    [persistNow],
  );

  return persistNow;
}
