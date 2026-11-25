import { useEffect, useState } from "react";
import type { SharedValue } from "react-native-reanimated";

import type { ActionFeedbackApi } from "@/contexts/actionFeedbackCore";
import { useLatestRef } from "@/lib/latestRef";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { createLiveTake, type LiveTake } from "@/features/speech/model/liveTake";
import { dictationFailureKey, dictationNeedsPlan } from "@/features/speech/model/voiceRefusal";
import { offerSettings } from "@/ui/overlay/dialogs";

type Say = {
  feedback: ActionFeedbackApi | null;
  t: (key: string) => string;
  onPlanRequired?: () => void;
};

/** A refused or failed dictation: the plans for `not_in_plan`, else its message. */
export function sayDictationFailure(error: unknown, { feedback, t, onPlanRequired }: Say): void {
  if (dictationNeedsPlan(error) && onPlanRequired) {
    onPlanRequired();
    return;
  }
  const failure = dictationFailureKey(error);
  if (failure) reportRecoverableError(feedback, t(failure));
}

type Options = Say & {
  token: string | null;
  meterLevel: SharedValue<number>;
  setRecording: (on: boolean) => void;
  setTranscribing: (on: boolean) => void;
  onTranscript: (text: string) => void;
};

/**
 * The composer mic's live take (`liveTake.ts`). Nothing of WebRTC loads here: the take
 * loads its call on the first mic tap, and says "fallback" where the app has none (Expo
 * Go), so the mic records a clip. Ended with the screen.
 */
export function useLiveTake(options: Options): LiveTake {
  const latest = useLatestRef(options);
  const [take] = useState(() =>
    createLiveTake({
      token: () => latest.current.token,
      setRecording: (on) => latest.current.setRecording(on),
      setTranscribing: (on) => latest.current.setTranscribing(on),
      setLevel: (level) => latest.current.meterLevel.set(level),
      onTranscript: (text) => latest.current.onTranscript(text),
      say: (key) => reportRecoverableError(latest.current.feedback, latest.current.t(key)),
      sayRefusal: (error) => sayDictationFailure(error, latest.current),
      // The OS asks only once; after a denial only Settings can turn it on.
      micDenied: () => void offerSettings("microphone"),
    }),
  );
  useEffect(() => () => take.cancel(), [take]);
  return take;
}
