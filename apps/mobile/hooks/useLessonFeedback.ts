import { useCallback, useEffect, useRef } from "react";
import { useLessonAudio } from "@/hooks/useLessonAudio";
import { notifySuccess, notifyWarning } from "@/lib/haptics";
import type { LessonAnswer } from "@/hooks/useLessonSession";

export function useLessonFeedback(
  answer: LessonAnswer | null,
  isCurrent: () => boolean,
  effectSound = true,
) {
  const audio = useLessonAudio(isCurrent);
  const played = useRef<string | null>(null);
  useEffect(() => {
    if (!answer || played.current === answer.attemptId || !isCurrent()) return;
    played.current = answer.attemptId;
    if (answer.correct) notifySuccess();
    else notifyWarning();
    if (effectSound) void audio.start("", "en", answer.correct);
  }, [answer, audio, effectSound, isCurrent]);
  const speak = useCallback(
    (word: string, language: string) => {
      if (isCurrent()) void audio.start(word, language);
    },
    [audio, isCurrent],
  );
  const celebrate = useCallback(() => {
    if (isCurrent() && effectSound) void audio.start("", "en", "complete");
  }, [audio, effectSound, isCurrent]);
  return { speak, celebrate, stop: audio.stop };
}
