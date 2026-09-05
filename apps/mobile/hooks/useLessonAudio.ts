import { useEffect, useMemo } from "react";
import { AppState } from "react-native";
import { createLessonAudio } from "@/lib/lessonAudio";

/** Pronunciation and practice effects belong to one focused visit. */
export function useLessonAudio(isCurrent: () => boolean) {
  const audio = useMemo(() => createLessonAudio(isCurrent), [isCurrent]);
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      if (state !== "active") audio.stop();
    });
    return () => {
      subscription.remove();
      audio.stop();
    };
  }, [audio]);
  return audio;
}
