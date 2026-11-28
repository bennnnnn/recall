import { useCallback, useLayoutEffect, useRef, type Dispatch, type SetStateAction } from "react";

import { useAuthOptional } from "@/contexts/AuthContext";
import type { UpgradeSource } from "@/features/billing/components/UpgradeSheet";
import { composerThreadKey } from "@/features/chat/model/composerThreadDraft";
import { useVoiceInput } from "@/features/speech/hooks/useVoiceInput";
import {
  dictationAnchor,
  draftWithDictation,
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
 * The composer mic: a take lands in the thread it was started in, at the caret where it
 * began (after the draft when the field was not being edited), never over text the user
 * had typed. A live take's words show on the waveform while they are spoken (the field is
 * hidden during a take) and reach the draft once, whole, at the stop: a take cancelled, a
 * chat left mid-take or a failed send restored never finds half-heard words in a draft.
 * A route change drops the open take, and a plan without dictation opens the plans
 * instead of recording.
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
  const caretRef = useRef<TextCaret | null>(null);

  /** The take's whole text, at the caret it began at. */
  const landTake = useCallback((text: string) => {
    if (voiceCaptureThreadRef.current !== composerThreadRef.current) return;
    const caret = caretRef.current;
    caretRef.current = null;
    setInput((prev) => draftWithDictation(dictationAnchor(prev, caret), text));
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
    onTranscript: landTake,
    // The server refused: the plan has no voice input (the app's copy was stale).
    onPlanRequired: () => openUpgrade("voice"),
    t,
  });

  useLayoutEffect(() => {
    cancelVoiceInput();
  }, [routeChatId, cancelVoiceInput]);

  // The launch cache holds the plan last seen: until the server says the plan, the take goes
  // and the server decides (its refusal opens the plans above), never an offer on a stale plan.
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
      caretRef.current = caret ?? null;
    }
    void toggleVoiceInput();
  }, [canDictate, toggleVoiceInput, voiceRecording, voiceTranscribing, openUpgrade, composerThreadRef]);

  return {
    voiceInputAvailable,
    voiceRecording,
    voiceTranscribing,
    voiceMeterLevel,
    toggleVoiceInput: handleToggleVoiceInput,
    cancelVoiceInput,
  };
}
