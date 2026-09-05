import { useEffect, useRef } from "react";
import { useLessonAudio } from "@/hooks/useLessonAudio";
import { notifySuccess, notifyWarning } from "@/lib/haptics";
import type { LessonAnswer } from "@/hooks/useLessonSession";

export function useLessonFeedback(answer: LessonAnswer | null, isCurrent: () => boolean) {
  const audio = useLessonAudio(isCurrent);
  const played = useRef<string | null>(null);
  useEffect(() => {
    if (!answer || played.current === answer.attemptId || !isCurrent()) return;
    played.current = answer.attemptId;
    if (answer.correct) notifySuccess();
    else notifyWarning();
    void audio.start("", "en", answer.correct);
  }, [answer, audio, isCurrent]);
  return {
    speak: (word: string, language: string) => {
      if (isCurrent()) void audio.start(word, language);
    },
    stop: audio.stop,
  };
}
