import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppState } from "react-native";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/contexts/AuthContext";
import { createLessonAudio } from "@/lib/lessonAudio";
import { prefFilePath, safePrefUserId } from "@/lib/filePrefs";
import { loadLessonPreferences, saveLessonPreferences } from "@/lib/projects/lessonPreferences";
import { notifySuccess, notifyWarning } from "@/lib/haptics";
import type { LessonAnswer } from "@/hooks/useLessonSession";

export function useLessonFeedback(answer: LessonAnswer | null, isCurrent: () => boolean) {
  const { user } = useAuth();
  const { t, i18n } = useTranslation();
  const [sound, setSound] = useState(true);
  const [voice, setVoice] = useState(false);
  const prefs = useRef({ sound: true, voice: false });
  const changed = useRef(false);
  const path = prefFilePath(`recall.lesson-feedback.${safePrefUserId(user?.id ?? "guest")}.json`);
  const audio = useMemo(() => createLessonAudio(isCurrent), [isCurrent]);
  const played = useRef<string | null>(null);
  useEffect(() => {
    let current = true;
    void loadLessonPreferences(path).then((value) => {
      if (!current || !isCurrent() || changed.current) return;
      prefs.current = value;
      setSound(value.sound);
      setVoice(value.voice);
    });
    return () => {
      current = false;
    };
  }, [path, isCurrent]);
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      if (state !== "active") audio.stop();
    });
    return () => {
      subscription.remove();
      audio.stop();
    };
  }, [audio]);
  useEffect(() => {
    if (!answer || played.current === answer.attemptId || !isCurrent()) return;
    played.current = answer.attemptId;
    if (answer.correct) notifySuccess();
    else notifyWarning();
    void audio.start(
      voice ? t(answer.correct ? "lesson.correct" : "lesson.try_again") : "",
      i18n.language,
      sound ? answer.correct : undefined,
    );
  }, [answer, audio, sound, voice, t, i18n.language, isCurrent]);
  const toggle = useCallback(
    (kind: "sound" | "voice") => {
      if (!isCurrent()) return;
      changed.current = true;
      prefs.current = { ...prefs.current, [kind]: !prefs.current[kind] };
      setSound(prefs.current.sound);
      setVoice(prefs.current.voice);
      audio.stop();
      void saveLessonPreferences(path, prefs.current);
    },
    [audio, path, isCurrent],
  );
  return {
    sound,
    voice,
    toggleSound: () => toggle("sound"),
    toggleVoice: () => toggle("voice"),
    speak: (word: string, language: string) => {
      if (isCurrent()) void audio.start(word, language);
    },
    stop: audio.stop,
  };
}
