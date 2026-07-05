import { useCallback, useEffect, useRef, useState } from "react";

import { api, type Message, type ProjectDailyQuiz, type ProjectQuizQuestion, type QuizModality } from "@/lib/api";

type Params = {
  token: string | null;
  projectId: string | null;
  chatId: string | null;
  enabled: boolean;
  onFeedback: (feedback: string) => void;
  onProgress?: (answered: number, goal: number) => void;
  onSuggestMcq?: () => void;
};

const MAX_TEXT_ATTEMPTS = 2;

export function useDailyQuiz({
  token,
  projectId,
  chatId,
  enabled,
  onFeedback,
  onProgress,
  onSuggestMcq,
}: Params) {
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [session, setSession] = useState<ProjectDailyQuiz | null>(null);
  const [modality, setModality] = useState<QuizModality>("mcq");
  const [error, setError] = useState<string | null>(null);
  const [allowRetry, setAllowRetry] = useState(false);
  const attemptCounts = useRef<Record<string, number>>({});

  const resetQuestionState = useCallback((questionId: string | null) => {
    setAllowRetry(false);
    if (questionId) {
      delete attemptCounts.current[questionId];
    }
  }, []);

  const load = useCallback(async () => {
    if (!token || !projectId || !enabled) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.ensureDailyQuiz(token, projectId);
      setSession(data);
      onProgress?.(data.answered_count, data.daily_goal);
      if (data.current?.id) {
        resetQuestionState(data.current.id);
      }
    } catch {
      setError("load_failed");
    } finally {
      setLoading(false);
    }
  }, [token, projectId, enabled, onProgress, resetQuestionState]);

  useEffect(() => {
    void load();
  }, [load]);

  const applyResult = useCallback(
    (result: Awaited<ReturnType<typeof api.answerDailyQuiz>>, prev: ProjectDailyQuiz | null) => {
      if (!prev) return prev;
      const answered = result.is_correct ? prev.answered_count + 1 : prev.answered_count;
      onProgress?.(answered, prev.daily_goal);
      const nextQuestion = result.batch_complete ? null : result.next_question;
      if (nextQuestion?.id) {
        resetQuestionState(nextQuestion.id);
      }
      return {
        ...prev,
        answered_count: answered,
        complete: result.batch_complete,
        current: nextQuestion,
      };
    },
    [onProgress, resetQuestionState],
  );

  const submitAnswer = useCallback(
    async (question: ProjectQuizQuestion, payload: { modality: QuizModality; letter?: string; text?: string }) => {
      if (!token || !projectId || submitting) return;
      setSubmitting(true);
      setError(null);
      try {
        const result = await api.answerDailyQuiz(token, projectId, question.id, {
          modality: payload.modality,
          letter: payload.letter,
          text: payload.text,
          chat_id: chatId ?? undefined,
        });
        onFeedback(result.feedback);
        if (result.allow_retry) {
          const attempts = (attemptCounts.current[question.id] ?? 0) + 1;
          attemptCounts.current[question.id] = attempts;
          setAllowRetry(true);
          if (attempts >= MAX_TEXT_ATTEMPTS || result.suggest_mcq) {
            setModality("mcq");
            onSuggestMcq?.();
          }
          setSession((prev) => (prev ? { ...prev, current: result.next_question ?? question } : prev));
        } else {
          setAllowRetry(false);
          setSession((prev) => applyResult(result, prev));
        }
      } catch {
        setError("submit_failed");
      } finally {
        setSubmitting(false);
      }
    },
    [token, projectId, chatId, submitting, onFeedback, onSuggestMcq, applyResult],
  );

  const skipQuestion = useCallback(
    async (question: ProjectQuizQuestion) => {
      if (!token || !projectId || submitting) return;
      setSubmitting(true);
      setError(null);
      try {
        const result = await api.answerDailyQuiz(token, projectId, question.id, {
          skip: true,
          chat_id: chatId ?? undefined,
        });
        onFeedback(result.feedback);
        setAllowRetry(false);
        resetQuestionState(result.next_question?.id ?? null);
        setSession((prev) => applyResult(result, prev));
      } catch {
        setError("submit_failed");
      } finally {
        setSubmitting(false);
      }
    },
    [token, projectId, chatId, submitting, onFeedback, applyResult, resetQuestionState],
  );

  return {
    loading,
    submitting,
    session,
    modality,
    setModality,
    allowRetry,
    error,
    reload: load,
    submitAnswer,
    skipQuestion,
  };
}

export function appendQuizFeedbackMessage(
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>,
  feedback: string,
) {
  setMessages((prev) => [
    ...prev,
    {
      id: `local-quiz-${Date.now()}`,
      role: "assistant",
      content: feedback,
      model: null,
      created_at: new Date().toISOString(),
    },
  ]);
}
