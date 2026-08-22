import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAuthToken } from "@/contexts/AuthContext";
import { useHome } from "@/contexts/HomeContext";
import { useProjects } from "@/contexts/ProjectsContext";
import { useProjectDetail } from "@/hooks/useProjectDetail";
import { api } from "@/lib/api";
import { invalidateProjectDetail } from "@/lib/cache/projectDetailCache";
import { takeQueuedLessonLaunch } from "@/lib/lessonLaunch";
import type { QuizChoice } from "@/lib/parseVocabQuiz";
import { buildChapterDrills, lessonWordProgress, type DrillStep } from "@/lib/projects/chapterDrill";
import {
  chapterItems,
  chapterProgress,
  chapterQueue,
  resolveLessonChapter,
} from "@/lib/projects/chapterLesson";

export type LessonFeedback = {
  correct: boolean;
  word: string;
  meaning: string;
  body: string;
};

export function useLessonSession(projectId: string) {
  const token = useAuthToken();
  const { t } = useTranslation();
  const { project, loading: projectLoading, load } = useProjectDetail(projectId);
  const { refresh: refreshProjects } = useProjects();
  const { refresh: refreshHome } = useHome();
  const requestedRef = useRef<string | null>(null);
  const seededRef = useRef(false);
  if (requestedRef.current === null) {
    const launch = takeQueuedLessonLaunch();
    requestedRef.current =
      launch?.projectId === projectId ? launch.chapter?.trim() || "" : "";
  }
  const [chapter, setChapter] = useState<string | null>(
    requestedRef.current || null,
  );
  const [drills, setDrills] = useState<DrillStep[]>([]);
  const [index, setIndex] = useState(0);
  const [missed, setMissed] = useState<Set<string>>(() => new Set());
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<LessonFeedback | null>(null);
  const [saving, setSaving] = useState(false);

  const labels = useMemo(
    () => ({
      useQuestion: (meaning: string) => t("lesson.quiz_use", { meaning }),
      meaningQuestion: (word: string) => t("lesson.quiz_meaning", { word }),
    }),
    [t],
  );

  useEffect(() => {
    if (!project) return;
    const title = resolveLessonChapter(project, requestedRef.current);
    if (!title) return;
    setChapter(title);
    const items = chapterQueue(chapterItems(project, title));
    // Distractor pool = ALL chapter items (mastered + pending), not just the
    // pending subset. Using only pending items shrinks the pool near chapter
    // completion, triggering wrong-language English fallback words.
    const pool = chapterItems(project, title);
    if (!seededRef.current || (drills.length === 0 && items.length > 0)) {
      setDrills(buildChapterDrills(items, pool, labels));
      setIndex(0);
      seededRef.current = true;
    }
  }, [drills.length, labels, project]);

  const step = drills[index] ?? null;
  const words = lessonWordProgress(drills, index);
  const currentNumber = words.current;
  const total = words.total;
  const progressFill = words.fill;
  const empty = Boolean(project && seededRef.current && drills.length === 0);
  // Local queue exhausted — every word this session was shown got saved. This
  // is NOT the same as the chapter being done: the queue was only ever built
  // from whatever was pending when the session started, so a chapter can have
  // untouched words left (from an earlier partial session, or catalog seeding
  // still catching up) even after this session's own queue is fully cleared.
  const queueDone = Boolean(seededRef.current && drills.length > 0 && index >= drills.length);
  const chapterDone = Boolean(
    project && chapter && chapterProgress(project, chapter)?.complete,
  );
  const complete = queueDone && chapterDone;
  // Session ended but the chapter (per the server's own completion check —
  // the same one driving the map's checkmarks) isn't actually done yet.
  const sessionEndedEarly = queueDone && !chapterDone;

  const refreshLearning = useCallback(() => {
    invalidateProjectDetail(projectId);
    void load({ silent: true, force: true });
    void refreshProjects({ silent: true, force: true });
    void refreshHome({ silent: true, force: true });
  }, [load, projectId, refreshHome, refreshProjects]);

  const finishWord = useCallback(
    async (itemId: string, failed: boolean): Promise<boolean> => {
      if (!token) return false;
      setError(null);
      try {
        await api.updateProjectItem(token, projectId, itemId, {
          status: failed ? "learning" : "mastered",
          ...(failed ? { was_correct: false } : {}),
        });
        refreshLearning();
        return true;
      } catch {
        setError(t("lesson.save_failed"));
        return false;
      }
    },
    [projectId, refreshLearning, t, token],
  );

  // Awaits the save before advancing — a failed save must not let the local
  // queue index (and therefore `complete`) move past it. On failure this
  // leaves `feedback` set so the result sheet stays up with the error and a
  // retry (tapping Continue again re-attempts the same word). `saving` stays
  // true for the whole call (not just the save itself) so the Continue
  // button stays disabled/loading through the end-of-queue confirmation
  // fetch too — otherwise a double-tap there could race two advances.
  const continueLesson = useCallback(async () => {
    setSaving(true);
    try {
      const current = drills[index];
      if (current?.kind === "meaning") {
        const saved = await finishWord(current.itemId, missed.has(current.itemId));
        if (!saved) return;
      }
      if (index + 1 >= drills.length) {
        // Last word of this session's queue — force a fresh fetch so the
        // queueDone-vs-chapterDone check above isn't judged against
        // pre-save project data (finishWord's own refresh is fire-and-forget).
        invalidateProjectDetail(projectId);
        await load({ silent: true, force: true });
      }
      setFeedback(null);
      setIndex((value) => value + 1);
    } finally {
      setSaving(false);
    }
  }, [drills, finishWord, index, load, missed, projectId]);

  const submitLetter = useCallback(
    (letter: QuizChoice["letter"]) => {
      if (!step || (step.kind !== "use" && step.kind !== "meaning") || feedback) {
        return;
      }
      const correct = step.quiz.correct === letter;
      const picked = step.quiz.choices.find((choice) => choice.letter === letter);
      setFeedback({
        correct,
        word: step.quiz.word,
        meaning: picked?.text ?? "",
        body: "",
      });
    },
    [feedback, step],
  );

  const recordWrongAttempt = useCallback(() => {
    if (!step) return;
    setMissed((prev) => new Set(prev).add(step.itemId));
  }, [step]);

  return {
    project,
    chapter,
    step,
    feedback,
    error,
    empty,
    complete,
    sessionEndedEarly,
    currentNumber,
    total,
    progressFill,
    busy: saving || (projectLoading && !project),
    streaming: saving,
    submitLetter,
    continueLesson,
    continueTeach: continueLesson,
    recordWrongAttempt,
  };
}
