import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { randomUUID } from "expo-crypto";
import { useTranslation } from "react-i18next";
import { useAuthToken } from "@/contexts/AuthContext";
import { useProjects } from "@/contexts/ProjectsContext";
import { useProjectDetail } from "@/hooks/useProjectDetail";
import { api } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { fetchProjectDetail, updateProjectDetailCache } from "@/lib/cache/projectDetailCache";
import { peekQueuedLessonLaunch, takeQueuedLessonLaunch } from "@/lib/lessonLaunch";
import type { QuizChoice } from "@/lib/parseVocabQuiz";
import { buildChapterDrills, isLastStepForWord, type DrillStep } from "@/lib/projects/chapterDrill";
import {
  chapterItems,
  chapterIsComplete,
  chapterQueue,
  resolveLessonChapter,
} from "@/lib/projects/chapterLesson";
import { branchAccess, domainAccess, groupPathByDomain } from "@/lib/projects/domainPath";
import { resolveDailyGoal } from "@/lib/projects/dailyGoals";
import { beginPractice, isPracticePending, subscribePractice } from "@/lib/projects/practiceState";

export type { DrillStep };
export type LessonAnswer = {
  letter: QuizChoice["letter"];
  correct: boolean;
  attemptId: string;
  itemId: string;
  completesWord: boolean;
  status: "saving" | "failed" | "saved";
};
type SessionState = {
  drills: DrillStep[];
  chapter: string | null;
  index: number;
  answer: LessonAnswer | null;
  seeded: boolean;
  reviewing: boolean;
  learned: number;
  reviewed: number;
};
const emptyState = (): SessionState => ({
  drills: [],
  chapter: null,
  index: 0,
  answer: null,
  seeded: false,
  reviewing: false,
  learned: 0,
  reviewed: 0,
});
const always = () => true;

export function useLessonSession(projectId: string, isCurrentView: () => boolean = always) {
  const token = useAuthToken();
  const tokenRef = useRef(token);
  tokenRef.current = token;
  const session = getSessionGeneration();
  const owner = useMemo(() => ({ session, projectId }), [session, projectId]);
  const ownerRef = useRef(owner);
  ownerRef.current = owner;
  const { project, loading, loadError, load, isCurrentOwner } = useProjectDetail(projectId);
  const { refresh: refreshProjects } = useProjects();
  const { t } = useTranslation();
  const requested = useMemo(() => peekQueuedLessonLaunch(owner.projectId)?.chapter, [owner]);
  const [state, setState] = useState({ owner, ...emptyState() });
  const view = state.owner === owner ? state : { owner, ...emptyState() };
  const latest = useRef(view);
  latest.current = view;
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const sameAccount = useCallback(() => owner.session === getSessionGeneration(), [owner]);
  const canAct = useCallback(
    () =>
      mounted.current &&
      ownerRef.current === owner &&
      sameAccount() &&
      isCurrentOwner() &&
      isCurrentView(),
    [owner, sameAccount, isCurrentOwner, isCurrentView],
  );
  const [, changed] = useState(0);
  useEffect(
    () =>
      subscribePractice(() => {
        if (canAct()) changed((value) => value + 1);
      }),
    [canAct],
  );
  const publish = useCallback(
    (next: SessionState) => {
      if (!canAct()) return;
      const value = { ...next, owner };
      latest.current = value;
      setState(value);
    },
    [canAct, owner],
  );
  const seededProject = useRef(project);
  useEffect(() => {
    if (!project || !canAct()) return;
    if (
      latest.current.seeded &&
      (latest.current.drills.length > 0 || seededProject.current === project)
    )
      return;
    seededProject.current = project;
    const chapter = resolveLessonChapter(project, requested);
    if (!chapter) {
      publish({ ...emptyState(), seeded: true });
      return;
    }
    const domains = groupPathByDomain(project.path_progress ?? []);
    const domain = domains.find((entry) => entry.chapters.some((row) => row.title === chapter));
    const chapterRow = domain?.chapters.find((row) => row.title === chapter);
    const locked = domain
      ? domainAccess(domains, domain.title, project.up_next) === "locked"
      : false;
    if (chapterRow && branchAccess(chapterRow, project.up_next, locked) === "locked") {
      publish({ ...emptyState(), seeded: true });
      return;
    }
    const words = chapterItems(project, chapter);
    const reviewing = chapterIsComplete(words);
    const queue = chapterQueue(words, resolveDailyGoal(project.daily_goal));
    const drills = buildChapterDrills(
      queue,
      project.lists.flatMap((group) => group.items),
      {
        useQuestion: (sentence) => t("lesson.quiz_use", { sentence }),
        meaningQuestion: (word) => t("lesson.meaning_question", { word }),
      },
    );
    publish({ ...emptyState(), chapter, drills, reviewing, seeded: true });
    if (peekQueuedLessonLaunch(projectId)) takeQueuedLessonLaunch();
  }, [project, projectId, requested, t, publish, canAct]);
  const step = view.drills[view.index] ?? null;

  const saveAnswer = useCallback(
    async (answer: LessonAnswer) => {
      if (!tokenRef.current || !canAct()) return;
      const release = beginPractice(answer.itemId, owner.session);
      if (!release) return;
      const savedToken = tokenRef.current;
      const previous = latest.current;
      publish({ ...previous, answer: { ...answer, status: "saving" } });
      try {
        const result = await api.recordProjectPractice(savedToken, projectId, answer.itemId, {
          attempt_id: answer.attemptId,
          was_correct: answer.correct,
          completes_word: answer.completesWord,
        });
        if (sameAccount()) {
          updateProjectDetailCache(
            projectId,
            (detail) => ({
              ...detail,
              lists: detail.lists.map((group) => ({
                ...group,
                items: group.items.map((item) => (item.id === result.item.id ? result.item : item)),
              })),
            }),
            owner.session,
          );
          void fetchProjectDetail(savedToken, projectId, { force: true, afterPending: true });
          void refreshProjects({ silent: true, force: true, afterPending: true });
        }
        if (!canAct() || latest.current.answer?.attemptId !== answer.attemptId) return;
        const next = latest.current;
        publish({
          ...next,
          answer: { ...answer, status: "saved" },
          learned: next.learned + (answer.completesWord && result.newly_mastered ? 1 : 0),
          reviewed: next.reviewed + (answer.completesWord && !result.newly_mastered ? 1 : 0),
        });
      } catch {
        if (canAct() && latest.current.answer?.attemptId === answer.attemptId)
          publish({ ...latest.current, answer: { ...answer, status: "failed" } });
      } finally {
        release();
      }
    },
    [canAct, owner, projectId, publish, sameAccount, refreshProjects],
  );

  const submitLetter = useCallback(
    (letter: QuizChoice["letter"]) => {
      if (!canAct() || !step || step.kind === "teach" || latest.current.index !== view.index)
        return;
      const previous = latest.current.answer;
      if (previous && (previous.status !== "saved" || previous.correct)) return;
      if (
        isPracticePending(step.itemId) ||
        !step.quiz.choices.some((choice) => choice.letter === letter)
      )
        return;
      const correct = letter === step.quiz.correct;
      const answer: LessonAnswer = {
        letter,
        correct,
        attemptId: randomUUID(),
        itemId: step.itemId,
        completesWord: correct && isLastStepForWord(view.drills, view.index),
        status: "saving",
      };
      void saveAnswer(answer);
    },
    [canAct, step, view.index, view.drills, saveAnswer],
  );
  const continueLesson = useCallback(() => {
    if (!canAct() || !step || latest.current.index !== view.index) return;
    const answer = latest.current.answer;
    if (step.kind !== "teach" && (!answer?.correct || answer.status !== "saved")) return;
    publish({ ...latest.current, index: latest.current.index + 1, answer: null });
  }, [canAct, step, view.index, publish]);
  const retryAnswer = useCallback(() => {
    const answer = latest.current.answer;
    if (answer?.status === "failed") void saveAnswer(answer);
  }, [saveAnswer]);
  const total = new Set(view.drills.map((entry) => entry.itemId)).size;
  const finished = view.seeded && total > 0 && view.index >= view.drills.length;
  const finishedWords = view.learned + view.reviewed;
  return {
    project,
    step,
    chapter: view.chapter,
    answer: view.answer,
    learned: view.learned,
    reviewed: view.reviewed,
    error: view.answer?.status === "failed" ? t("lesson.save_failed") : null,
    loadError,
    load,
    empty: view.seeded && total === 0,
    complete: finished,
    reviewing: view.reviewing,
    busy: loading && !project,
    saving: Boolean(step && isPracticePending(step.itemId)),
    currentNumber: Math.min(total, finishedWords + (finished ? 0 : 1)),
    total,
    progressFill: total ? finishedWords / total : 0,
    canAdvance: step?.kind === "teach" || (view.answer?.correct && view.answer.status === "saved"),
    submitLetter,
    continueLesson,
    retryAnswer,
  };
}
