import { useCallback, useEffect, useState } from "react";

import {
  DEFAULT_LESSON_PREFS,
  getLessonPrefs,
  lessonTextScale,
  setLessonPrefs,
  type LessonPrefs,
} from "@/lib/lessonPrefs";

export function useLessonPrefs() {
  const [prefs, setPrefs] = useState(DEFAULT_LESSON_PREFS);
  useEffect(() => {
    let live = true;
    void getLessonPrefs().then((value) => {
      if (live) setPrefs(value);
    });
    return () => {
      live = false;
    };
  }, []);
  const updatePrefs = useCallback((patch: Partial<LessonPrefs>) => {
    setPrefs((previous) => {
      const next = { ...previous, ...patch };
      void setLessonPrefs(next);
      return next;
    });
  }, []);
  return { prefs, updatePrefs, textScale: lessonTextScale(prefs.fontSize) };
}
