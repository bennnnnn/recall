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
import {
  buildChapterDrills,
  isLastStepForWord,
  type DrillStep,
} from "@/lib/projects/chapterDrill";
import {
  chapterIsComplete,
  chapterItems,
  chapterQueue,
  groupLessonProgress,
  overlayMasteredItems,
  resolveLessonChapter,
} from "@/lib/projects/chapterLesson";
import { resolveDailyGoal } from "@/lib/projects/dailyGoals";

export type { DrillStep };

export function useLessonSession(projectId: string) {
  const token = useAuthToken();
  const { t } = useTranslation();
  const { project, loading: projectLoading, load } = useProjectDetail(projectId);
  const { refresh: refreshProjects } = useProjects();
  const { refresh: refreshHome } = useHome();
  const requestedRef = useRef<string | null>(null);
  const seededRef = useRef(false);
  const advancingRef = useRef(false);
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
  const [masteredIds, setMasteredIds] = useState<Record<string, true>>({});
  const [quizSolved, setQuizSolved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [reviewing, setReviewing] = useState(false);

  const labels = useMemo(
    () => ({
      useQuestion: (sentence: string) => t("lesson.quiz_use", { sentence }),
      meaningQuestion: (sentence: string) => t("lesson.quiz_meaning", { sentence }),
    }),
    [t],
  );

  useEffect(() => {
    if (!project) return;
    const title = resolveLessonChapter(project, requestedRef.current);
    if (!title) return;
    setChapter(title);
    const chapterWords = chapterItems(project, title);
    const isReview = chapterIsComplete(chapterWords);
    const items = chapterQueue(
      chapterWords,
      isReview ? undefined : resolveDailyGoal(project.daily_goal),
    );
    if (!seededRef.current || (drills.length === 0 && items.length > 0)) {
      setDrills(buildChapterDrills(items, chapterWords, labels));
      setIndex(0);
      setQuizSolved(false);
      setReviewing(isReview);
      seededRef.current = true;
    }
  }, [drills.length, labels, project]);

  const overlayItems = useMemo(() => {
    if (!project || !chapter) return [];
    return overlayMasteredItems(chapterItems(project, chapter), masteredIds);
  }, [chapter, masteredIds, project]);

  const step = drills[index] ?? null;
  const words = groupLessonProgress(overlayItems, step?.itemId ?? null);
  const currentNumber = words.current;
  const total = words.total;
  const progressFill = words.fill;
  const empty = Boolean(project && seededRef.current && drills.length === 0);
  const queueDone = Boolean(seededRef.current && drills.length > 0 && index >= drills.length);
  const chapterDone = chapterIsComplete(overlayItems);
  const complete = queueDone && chapterDone;
  const sessionEndedEarly = queueDone && !chapterDone;
  const canAdvance = step?.kind === "teach" || (step != null && quizSolved);

  const refreshLearning = useCallback(() => {
    invalidateProjectDetail(projectId);
    void load({ silent: true, force: true });
    void refreshProjects({ silent: true, force: true });
    void refreshHome({ silent: true, force: true });
  }, [load, projectId, refreshHome, refreshProjects]);

  const finishWord = useCallback(
    async (itemId: string): Promise<boolean> => {
      if (!token || !project || !chapter) return false;
      const item = chapterItems(project, chapter).find((row) => row.id === itemId);
      if (item?.status === "mastered" || item?.mastered) return true;
      setSaving(true);
      setError(null);
      setMasteredIds((prev) => ({ ...prev, [itemId]: true }));
      try {
        await api.updateProjectItem(token, projectId, itemId, { status: "mastered" });
        refreshLearning();
        return true;
      } catch {
        setMasteredIds((prev) => {
          const next = { ...prev };
          delete next[itemId];
          return next;
        });
        setError(t("lesson.save_failed"));
        return false;
      } finally {
        setSaving(false);
      }
    },
    [chapter, project, projectId, refreshLearning, t, token],
  );

  const continueLesson = useCallback(() => {
    if (!step || advancingRef.current) return;
    if (step.kind !== "teach" && !quizSolved) return;
    advancingRef.current = true;
    const itemId = step.itemId;
    const shouldSave = isLastStepForWord(drills, index);
    void (async () => {
      if (shouldSave) {
        const saved = await finishWord(itemId);
        if (!saved) {
          advancingRef.current = false;
          return;
        }
      }
      setQuizSolved(false);
      setIndex((value) => value + 1);
      advancingRef.current = false;
    })();
  }, [drills, finishWord, index, quizSolved, step]);

  const submitLetter = useCallback((_letter: QuizChoice["letter"]) => {
    setQuizSolved(true);
  }, []);

  return {
    project,
    chapter,
    step,
    error,
    empty,
    complete,
    sessionEndedEarly,
    reviewing,
    currentNumber,
    total,
    progressFill,
    busy: projectLoading && !project,
    saving,
    canAdvance,
    submitLetter,
    continueLesson,
  };
}
