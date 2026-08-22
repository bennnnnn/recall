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
  const complete = Boolean(seededRef.current && drills.length > 0 && index >= drills.length);

  const refreshLearning = useCallback(() => {
    invalidateProjectDetail(projectId);
    void load({ silent: true, force: true });
    void refreshProjects({ silent: true, force: true });
    void refreshHome({ silent: true, force: true });
  }, [load, projectId, refreshHome, refreshProjects]);

  const finishWord = useCallback(
    async (itemId: string, failed: boolean) => {
      if (!token) return;
      setSaving(true);
      try {
        await api.updateProjectItem(token, projectId, itemId, {
          status: failed ? "learning" : "mastered",
          ...(failed ? { was_correct: false } : {}),
        });
        refreshLearning();
      } catch {
        setError(t("projects.study_launch_failed"));
      } finally {
        setSaving(false);
      }
    },
    [projectId, refreshLearning, t, token],
  );

  const continueLesson = useCallback(() => {
    const current = drills[index];
    setFeedback(null);
    if (current?.kind === "meaning") {
      void finishWord(current.itemId, missed.has(current.itemId));
    }
    setIndex((value) => value + 1);
  }, [drills, finishWord, index, missed]);

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
