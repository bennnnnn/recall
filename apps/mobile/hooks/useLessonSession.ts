import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAuthToken } from "@/contexts/AuthContext";
import { useHome } from "@/contexts/HomeContext";
import { useProjects } from "@/contexts/ProjectsContext";
import { useChat } from "@/hooks/useChat";
import { useProjectDetail } from "@/hooks/useProjectDetail";
import { api } from "@/lib/api";
import { invalidateProjectDetail } from "@/lib/cache/projectDetailCache";
import { takeQueuedLessonLaunch } from "@/lib/lessonLaunch";
import { deriveLessonStep, latestAssistantProse, type LessonStep } from "@/lib/lessonStep";
import { buildProjectAskPromptFromProject } from "@/lib/projects/projectChat";
import type { QuizChoice } from "@/lib/parseVocabQuiz";

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
  const [chatId, setChatId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<LessonFeedback | null>(null);
  const [typed, setTyped] = useState("");
  const startedRef = useRef(false);
  const sendWhenReadyRef = useRef<string | null>(null);
  const awaitingHintRef = useRef(false);
  const pendingTypedRef = useRef<{ word: string; meaning: string } | null>(null);

  const { messages, streaming, finalizing, sendMessage } = useChat(token, chatId, {
    onError: (message) => {
      awaitingHintRef.current = false;
      setError(message);
    },
    onFirstReply: () => {
      invalidateProjectDetail(projectId);
      void load({ silent: true, force: true });
      void refreshProjects({ silent: true, force: true });
      void refreshHome({ silent: true, force: true });
    },
  });

  const start = useCallback(
    async (prompt: string) => {
      if (!token || startedRef.current) return;
      const trimmed = prompt.trim();
      if (!trimmed) return;
      startedRef.current = true;
      setError(null);
      try {
        const chat = await api.createChat(token, "auto", projectId, "chat");
        sendWhenReadyRef.current = trimmed;
        setChatId(chat.id);
      } catch {
        startedRef.current = false;
        setError(t("projects.study_launch_failed"));
      }
    },
    [projectId, t, token],
  );

  useEffect(() => {
    const prompt = sendWhenReadyRef.current;
    if (!chatId || !prompt) return;
    sendWhenReadyRef.current = null;
    void sendMessage(prompt);
  }, [chatId, sendMessage]);

  useEffect(() => {
    if (startedRef.current) return;
    const queued = takeQueuedLessonLaunch();
    if (queued && queued.projectId === projectId && queued.prompt) {
      void start(queued.prompt);
      return;
    }
    if (project) {
      void start(buildProjectAskPromptFromProject(project, t));
    }
  }, [project, projectId, start, t]);

  const step: LessonStep = useMemo(
    () => deriveLessonStep(messages, { streaming: streaming || finalizing }),
    [finalizing, messages, streaming],
  );

  useEffect(() => {
    if (!awaitingHintRef.current || streaming || finalizing) return;
    awaitingHintRef.current = false;
    const prose = latestAssistantProse(messages);
    if (!prose) return;
    const typedMeta = pendingTypedRef.current;
    pendingTypedRef.current = null;
    setFeedback((prev) => {
      if (prev) return { ...prev, body: prose };
      if (!typedMeta) return prev;
      return {
        correct: !/\b(wrong|incorrect|not quite|try again)\b/i.test(prose),
        word: typedMeta.word,
        meaning: typedMeta.meaning,
        body: prose,
      };
    });
  }, [finalizing, messages, streaming]);

  const refreshLearning = useCallback(() => {
    invalidateProjectDetail(projectId);
    void load({ silent: true, force: true });
    void refreshProjects({ silent: true, force: true });
    void refreshHome({ silent: true, force: true });
  }, [load, projectId, refreshHome, refreshProjects]);

  const submitLetter = useCallback(
    (letter: QuizChoice["letter"]) => {
      if (!chatId || streaming || finalizing || step.kind !== "quiz") return;
      const choice = step.quiz.choices.find((item) => item.letter === letter);
      setFeedback({
        correct: step.quiz.correct === letter,
        word: step.quiz.word,
        meaning: choice?.text ?? "",
        body: "",
      });
      awaitingHintRef.current = true;
      refreshLearning();
      void sendMessage(letter);
    },
    [chatId, finalizing, refreshLearning, sendMessage, step, streaming],
  );

  const submitTyped = useCallback(() => {
    const answer = typed.trim();
    if (!chatId || streaming || finalizing || !answer) return;
    if (step.kind !== "vocab_card") return;
    pendingTypedRef.current = {
      word: step.card.word,
      meaning: step.card.definition,
    };
    awaitingHintRef.current = true;
    setTyped("");
    refreshLearning();
    void sendMessage(answer);
  }, [chatId, finalizing, refreshLearning, sendMessage, step, streaming, typed]);

  const continueLesson = useCallback(() => {
    setFeedback(null);
    setTyped("");
  }, []);

  const busy = streaming || finalizing || (projectLoading && !project && !startedRef.current);

  return {
    project,
    step,
    feedback,
    typed,
    setTyped,
    error,
    busy,
    streaming: streaming || finalizing,
    submitLetter,
    submitTyped,
    continueLesson,
  };
}
