import { useCallback, useLayoutEffect, useRef, type Dispatch, type SetStateAction } from "react";

import { useAuthOptional } from "@/contexts/AuthContext";
import type { UpgradeSource } from "@/features/billing/components/UpgradeSheet";
import { composerThreadKey } from "@/features/chat/model/composerThreadDraft";
import { useVoiceInput } from "@/features/speech/hooks/useVoiceInput";
import {
  appendDictation,
  dictationAnchor,
  draftWithDictation,
  type DictationAnchor,
  type TextCaret,
} from "@/features/chat/model/dictationDraft";
import type { User } from "@/lib/api";
import { hasPlanFeature } from "@/lib/plan";
import { useLatestRef } from "@/lib/latestRef";

type Options = {
  token: string | null;
  user: User | null;
  routeChatId: string | undefined;
  setInput: Dispatch<SetStateAction<string>>;
  /** Opens the plans: a plan without dictation, or the server's refusal of a take. */
  openUpgrade: (source: UpgradeSource) => void;
  t: (key: string) => string;
};

/**
 * Where a take's words go: the caret it began at, the draft split there (on its first
 * words), and every draft the take has written, so it knows a draft it may still rewrite.
 */
type TakeDraft = { caret: TextCaret | null; anchor: DictationAnchor | null; ours: Set<string> };

function newTake(caret: TextCaret | null): TakeDraft {
  return { caret, anchor: null, ours: new Set() };
}

/**
 * The composer mic: a take lands in the thread it was started in, at the caret where it
 * began (after the draft when the field was not being edited), word by word on a live take,
 * never over text the user had typed. A route change drops the open take, and a plan
 * without dictation opens the plans instead of recording.
 */
export function useComposerDictation({
  token,
  user,
  routeChatId,
  setInput,
  openUpgrade,
  t,
}: Options) {
  const composerThread = composerThreadKey(
    typeof routeChatId === "string" ? routeChatId : undefined,
  );
  const composerThreadRef = useLatestRef(composerThread);
  const voiceCaptureThreadRef = useRef(composerThread);
  const takeRef = useRef<TakeDraft>(newTake(null));

  /**
   * The take's text in the draft, each word replacing the last version of it. Once the draft
   * has changed under the take, only its final text lands, after whatever is there.
   */
  const writeTake = useCallback((text: string, final: boolean) => {
    if (voiceCaptureThreadRef.current !== composerThreadRef.current) return;
    const take = takeRef.current;
    // The final text ends the take: a later cancel leaves the draft as it now is.
    if (final) takeRef.current = newTake(null);
    setInput((prev) => {
      if (!take.anchor) {
        take.anchor = dictationAnchor(prev, take.caret);
        take.ours.add(prev);
      }
      if (!take.ours.has(prev)) return final ? appendDictation(prev, text) : prev;
      const next = draftWithDictation(take.anchor, text);
      take.ours.add(next);
      return next;
    });
  }, [composerThreadRef, setInput]);

  const {
    voiceInputAvailable,
    voiceRecording,
    voiceTranscribing,
    voiceMeterLevel,
    toggleVoiceInput,
    cancelVoiceInput,
  } = useVoiceInput({
    token,
    onLiveText: (text) => writeTake(text, false),
    onTranscript: (text) => writeTake(text, true),
    // The server refused: the plan has no voice input (the app's copy was stale).
    onPlanRequired: () => openUpgrade("voice"),
    t,
  });

  useLayoutEffect(() => {
    cancelVoiceInput();
  }, [routeChatId, cancelVoiceInput]);

  /** Cancel drops the take: a live take's words already in the draft come back out. */
  const cancelTake = useCallback(() => {
    cancelVoiceInput();
    const take = takeRef.current;
    takeRef.current = newTake(null);
    const anchor = take.anchor;
    if (!anchor || voiceCaptureThreadRef.current !== composerThreadRef.current) return;
    setInput((prev) => (take.ours.has(prev) ? anchor.original : prev));
  }, [cancelVoiceInput, composerThreadRef, setInput]);

  // The launch cache paints every plan "free": until the server says the plan, the take goes
  // and the server decides (its refusal opens the plans above), never a paid account's offer.
  const planKnown = useAuthOptional()?.profileValidated ?? true;
  const canDictate = !planKnown || hasPlanFeature(user, "speech_transcription");
  /** The mic. `caret` is the field's selection while it is being edited, else none. */
  const handleToggleVoiceInput = useCallback((caret?: TextCaret | null) => {
    if (!voiceRecording && !voiceTranscribing) {
      // Don't record what the plan cannot send; show the plans instead.
      if (!canDictate) {
        openUpgrade("voice");
        return;
      }
      voiceCaptureThreadRef.current = composerThreadRef.current;
      takeRef.current = newTake(caret ?? null);
    }
    void toggleVoiceInput();
  }, [canDictate, toggleVoiceInput, voiceRecording, voiceTranscribing, openUpgrade, composerThreadRef]);

  return {
    voiceInputAvailable,
    voiceRecording,
    voiceTranscribing,
    voiceMeterLevel,
    toggleVoiceInput: handleToggleVoiceInput,
    cancelVoiceInput: cancelTake,
  };
}
