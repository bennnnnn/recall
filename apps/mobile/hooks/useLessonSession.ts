import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAuthToken } from "@/contexts/AuthContext";
import { useHome } from "@/contexts/HomeContext";
import { useProjects } from "@/contexts/ProjectsContext";
import { useProjectDetail } from "@/hooks/useProjectDetail";
import { api, type ProjectItem } from "@/lib/api";
import { invalidateProjectDetail } from "@/lib/cache/projectDetailCache";
import { takeQueuedLessonLaunch } from "@/lib/lessonLaunch";
import {
  chapterIsComplete,
  chapterItems,
  chapterQueue,
  itemToCard,
  overlayItemOutcomes,
  resolveLessonChapter,
  type LessonVocabCard,
} from "@/lib/projects/chapterLesson";
import { resolveDailyGoal } from "@/lib/projects/dailyGoals";

export type LessonStep = {
  itemId: string;
  card: LessonVocabCard;
};

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
  const [queue, setQueue] = useState<ProjectItem[]>([]);
  const [index, setIndex] = useState(0);
  const [outcomes, setOutcomes] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!project) return;
    const title = resolveLessonChapter(project, requestedRef.current);
    if (!title) return;
    setChapter(title);
    const items = chapterQueue(
      chapterItems(project, title),
      resolveDailyGoal(project.daily_goal),
    );
    if (!seededRef.current || (queue.length === 0 && items.length > 0)) {
      setQueue(items);
      setIndex(0);
      seededRef.current = true;
    }
  }, [project, queue.length]);

  const overlayItems = useMemo(() => {
    if (!project || !chapter) return [];
    return overlayItemOutcomes(chapterItems(project, chapter), outcomes);
  }, [chapter, outcomes, project]);

  const current = queue[index] ?? null;
  const step: LessonStep | null = current
    ? { itemId: current.id, card: itemToCard(current) }
    : null;
  const total = queue.length;
  const currentNumber = total === 0 ? 0 : Math.min(index + 1, total);
  const progressFill = total === 0 ? 0 : index >= total ? 1 : index / total;
  const empty = Boolean(project && seededRef.current && queue.length === 0);
  const queueDone = Boolean(seededRef.current && queue.length > 0 && index >= queue.length);
  const chapterDone = chapterIsComplete(overlayItems);
  const complete = queueDone && chapterDone;
  const sessionEndedEarly = queueDone && !chapterDone;

  const refreshLearning = useCallback(() => {
    invalidateProjectDetail(projectId);
    void load({ silent: true, force: true });
    void refreshProjects({ silent: true, force: true });
    void refreshHome({ silent: true, force: true });
  }, [load, projectId, refreshHome, refreshProjects]);

  const rateWord = useCallback(
    async (known: boolean) => {
      if (!token || !current || advancingRef.current) return;
      advancingRef.current = true;
      setSaving(true);
      setError(null);
      const itemId = current.id;
      const failed = !known;
      const previousIndex = index;
      setOutcomes((prev) => ({ ...prev, [itemId]: failed }));
      setIndex(previousIndex + 1);
      try {
        await api.updateProjectItem(token, projectId, itemId, {
          status: failed ? "learning" : "mastered",
          ...(failed ? { was_correct: false } : {}),
        });
        refreshLearning();
      } catch {
        setOutcomes((prev) => {
          const next = { ...prev };
          delete next[itemId];
          return next;
        });
        setIndex(previousIndex);
        setError(t("lesson.save_failed"));
      } finally {
        setSaving(false);
        advancingRef.current = false;
      }
    },
    [current, index, projectId, refreshLearning, t, token],
  );

  return {
    project,
    chapter,
    step,
    error,
    empty,
    complete,
    sessionEndedEarly,
    currentNumber,
    total,
    progressFill,
    busy: projectLoading && !project,
    saving,
    rateKnown: () => void rateWord(true),
    rateNotYet: () => void rateWord(false),
  };
}
