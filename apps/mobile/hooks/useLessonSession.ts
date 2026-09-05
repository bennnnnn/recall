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
  groupLessonProgress,
  isItemMastered,
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
  status: "missed" | "saving" | "failed" | "saved";
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
  finishesGroup: boolean;
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
  finishesGroup: false,
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
    const pending = words.filter((item) => !isItemMastered(item));
    const queue = chapterQueue(words, resolveDailyGoal(project.daily_goal));
    const finishesGroup = reviewing || queue.length === pending.length;
    const drills = buildChapterDrills(
      queue,
      project.lists.flatMap((group) => group.items),
      {
        useQuestion: (sentence) => sentence,
        meaningQuestion: (word) => word,
      },
    );
    publish({ ...emptyState(), chapter, drills, reviewing, finishesGroup, seeded: true });
    if (peekQueuedLessonLaunch(projectId)) takeQueuedLessonLaunch();
  }, [project, projectId, requested, publish, canAct]);
  const step = view.drills[view.index] ?? null;

  const saveInFlight = useRef<Promise<void> | null>(null);
  const saveAnswer = useCallback(
    async (answer: LessonAnswer, quiet = false) => {
      if (!tokenRef.current || !canAct() || !answer.correct) return;
      const release = beginPractice(answer.itemId, owner.session);
      if (!release) return;
      const savedToken = tokenRef.current;
      const previous = latest.current;
      if (!quiet) publish({ ...previous, answer: { ...answer, status: "saving" } });
      const run = (async () => {
        try {
          const result = await api.recordProjectPractice(savedToken, projectId, answer.itemId, {
            attempt_id: answer.attemptId,
            was_correct: true,
            completes_word: answer.completesWord,
          });
          if (sameAccount()) {
            updateProjectDetailCache(
              projectId,
              (detail) => ({
                ...detail,
                lists: detail.lists.map((group) => ({
                  ...group,
                  items: group.items.map((item) =>
                    item.id === result.item.id ? result.item : item,
                  ),
                })),
              }),
              owner.session,
            );
            void fetchProjectDetail(savedToken, projectId, { force: true, afterPending: true });
            void refreshProjects({ silent: true, force: true, afterPending: true });
          }
          if (!canAct() || (!quiet && latest.current.answer?.attemptId !== answer.attemptId)) return;
          const next = latest.current;
          publish({
            ...next,
            answer: quiet ? null : { ...answer, status: "saved" },
            learned: next.learned + (answer.completesWord && result.newly_mastered ? 1 : 0),
            reviewed: next.reviewed + (answer.completesWord && !result.newly_mastered ? 1 : 0),
          });
        } catch {
          if (quiet) {
            if (canAct())
              publish({ ...latest.current, answer: { ...answer, status: "failed" } });
            return;
          }
          if (canAct() && latest.current.answer?.attemptId === answer.attemptId)
            publish({ ...latest.current, answer: { ...answer, status: "failed" } });
        } finally {
          release();
        }
      })();
      saveInFlight.current = run;
      try {
        await run;
      } finally {
        if (saveInFlight.current === run) saveInFlight.current = null;
      }
    },
    [canAct, owner, projectId, publish, sameAccount, refreshProjects],
  );

  const submitLetter = useCallback(
    (letter: QuizChoice["letter"]) => {
      if (!canAct() || !step || step.kind === "teach" || latest.current.index !== view.index)
        return;
      if (latest.current.reviewing) return;
      const previous = latest.current.answer;
      if (previous?.correct) return;
      if (previous && previous.status !== "missed") return;
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
        status: correct ? "saving" : "missed",
      };
      if (!correct) {
        publish({ ...latest.current, answer });
        return;
      }
      void saveAnswer(answer);
    },
    [canAct, step, view.index, view.drills, saveAnswer, publish],
  );
  const continueLesson = useCallback(async () => {
    if (!canAct() || !step) return;
    const startIndex = latest.current.index;
    if (startIndex !== view.index) return;
    const reviewing = latest.current.reviewing;
    if (step.kind !== "teach" && !reviewing) {
      const current = latest.current.answer;
      if (!current?.correct || current.status === "failed") return;
      if (current.status === "saving") await saveInFlight.current;
      const saved = latest.current.answer;
      if (
        latest.current.index !== startIndex ||
        !saved?.correct ||
        saved.status !== "saved"
      )
        return;
    }
    if (
      reviewing &&
      step.kind !== "teach" &&
      isLastStepForWord(latest.current.drills, startIndex)
    ) {
      const letter = step.quiz.correct;
      if (!letter) return;
      await saveAnswer(
        {
          letter,
          correct: true,
          attemptId: randomUUID(),
          itemId: step.itemId,
          completesWord: true,
          status: "saving",
        },
        true,
      );
      if (latest.current.index !== startIndex || latest.current.answer?.status === "failed")
        return;
    }
    publish({ ...latest.current, index: startIndex + 1, answer: null });
  }, [canAct, step, view.index, publish, saveAnswer]);
  const retryAnswer = useCallback(() => {
    const answer = latest.current.answer;
    if (answer?.status === "failed") void saveAnswer(answer, latest.current.reviewing);
  }, [saveAnswer]);
  const words = project && view.chapter ? chapterItems(project, view.chapter) : [];
  const total = new Set(view.drills.map((entry) => entry.itemId)).size;
  const finished = view.seeded && total > 0 && view.index >= view.drills.length;
  const progress = groupLessonProgress(words, step?.itemId ?? null);
  const groupDone = finished && (view.reviewing || view.finishesGroup || chapterIsComplete(words));
  const canAdvance = Boolean(
    step &&
      (step.kind === "teach" ||
        (view.reviewing && view.answer?.status !== "failed") ||
        (view.answer?.correct && view.answer.status !== "failed")),
  );
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
    groupDone,
    busy: loading && !project,
    saving: Boolean(step && isPracticePending(step.itemId)),
    currentNumber: groupDone ? progress.total : progress.current,
    total: progress.total,
    progressFill: groupDone ? 1 : progress.fill,
    canAdvance,
    submitLetter,
    continueLesson,
    retryAnswer,
  };
}
