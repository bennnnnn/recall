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
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [loadingNext, setLoadingNext] = useState(false);
  const [session, setSession] = useState<ProjectDailyQuiz | null>(null);
  const [modality, setModality] = useState<QuizModality>("mcq");
  const [error, setError] = useState<string | null>(null);
  const [allowRetry, setAllowRetry] = useState(false);
  const attemptCounts = useRef<Record<string, number>>({});
  const loadInFlightRef = useRef(false);
  const prefetchInFlightRef = useRef(false);

  const resetQuestionState = useCallback((questionId: string | null) => {
    setAllowRetry(false);
    if (questionId) {
      delete attemptCounts.current[questionId];
    }
  }, []);

  const prefetchQuiz = useCallback(async () => {
    if (!token || !projectId || prefetchInFlightRef.current) return;
    prefetchInFlightRef.current = true;
    try {
      await api.prefetchDailyQuiz(token, projectId);
    } catch {
      /* best-effort background prefetch */
    } finally {
      prefetchInFlightRef.current = false;
    }
  }, [token, projectId]);

  const refreshNextQuestion = useCallback(
    async (answeredCount: number) => {
      if (!token || !projectId) return;
      setLoadingNext(true);
      setError(null);
      try {
        await prefetchQuiz();
        let data = await api.getDailyQuiz(token, projectId);
        if (!data.complete && !data.current && data.answered_count < data.daily_goal) {
          data = await api.ensureDailyQuiz(token, projectId);
        }
        setSession((prev) =>
          prev
            ? {
                ...data,
                answered_count: answeredCount,
              }
            : data,
        );
        onProgress?.(answeredCount, data.daily_goal);
        if (data.current?.id) {
          resetQuestionState(data.current.id);
        }
        if (data.current && !data.complete) {
          void prefetchQuiz();
        }
      } catch {
        setError("load_failed");
      } finally {
        setLoadingNext(false);
      }
    },
    [token, projectId, onProgress, prefetchQuiz, resetQuestionState],
  );

  const load = useCallback(async () => {
    if (!token || !projectId || !enabled || loadInFlightRef.current) return;
    loadInFlightRef.current = true;
    setLoading(true);
    setError(null);
    try {
      let data = await api.getDailyQuiz(token, projectId);
      if (!data.complete && data.answered_count < data.daily_goal && !data.current) {
        data = await api.ensureDailyQuiz(token, projectId);
      }
      setSession(data);
      onProgress?.(data.answered_count, data.daily_goal);
      if (data.current?.id) {
        resetQuestionState(data.current.id);
      }
      if (data.current && !data.complete) {
        void prefetchQuiz();
      }
    } catch {
      setError("load_failed");
    } finally {
      loadInFlightRef.current = false;
      setLoading(false);
    }
  }, [token, projectId, enabled, onProgress, prefetchQuiz, resetQuestionState]);

  useEffect(() => {
    void load();
  }, [load]);

  const applyResult = useCallback(
    (result: Awaited<ReturnType<typeof api.answerDailyQuiz>>, prev: ProjectDailyQuiz | null) => {
      if (!prev) return prev;
      const answered = result.is_correct ? prev.answered_count + 1 : prev.answered_count;
      const nextQuestion = result.batch_complete ? null : result.next_question;
      return {
        ...prev,
        answered_count: answered,
        complete: result.batch_complete,
        current: nextQuestion,
      };
    },
    [],
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
          let answeredCount = session?.answered_count ?? 0;
          let dailyGoal = session?.daily_goal ?? 0;
          setSession((prev) => {
            const next = applyResult(result, prev);
            if (next) {
              answeredCount = next.answered_count;
              dailyGoal = next.daily_goal;
            }
            return next;
          });
          onProgress?.(answeredCount, dailyGoal);
          if (result.next_question?.id) {
            resetQuestionState(result.next_question.id);
          } else if (result.batch_complete) {
            resetQuestionState(null);
          }
          if (!result.batch_complete && !result.next_question) {
            void refreshNextQuestion(answeredCount);
          } else if (!result.batch_complete) {
            void prefetchQuiz();
          }
        }
      } catch {
        setError("submit_failed");
      } finally {
        setSubmitting(false);
      }
    },
    [
      token,
      projectId,
      chatId,
      submitting,
      session?.answered_count,
      onFeedback,
      onSuggestMcq,
      applyResult,
      refreshNextQuestion,
      prefetchQuiz,
      onProgress,
      resetQuestionState,
    ],
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
        let answeredCount = session?.answered_count ?? 0;
        let dailyGoal = session?.daily_goal ?? 0;
        setSession((prev) => {
          const next = applyResult(result, prev);
          if (next) {
            answeredCount = next.answered_count;
            dailyGoal = next.daily_goal;
          }
          return next;
        });
        onProgress?.(answeredCount, dailyGoal);
        if (result.next_question?.id) {
          resetQuestionState(result.next_question.id);
        } else if (result.batch_complete) {
          resetQuestionState(null);
        }
        if (!result.batch_complete && !result.next_question) {
          void refreshNextQuestion(answeredCount);
        } else if (!result.batch_complete) {
          void prefetchQuiz();
        }
      } catch {
        setError("submit_failed");
      } finally {
        setSubmitting(false);
      }
    },
    [
      token,
      projectId,
      chatId,
      submitting,
      session?.answered_count,
      onFeedback,
      applyResult,
      resetQuestionState,
      refreshNextQuestion,
      prefetchQuiz,
      onProgress,
      resetQuestionState,
    ],
  );

  return {
    loading,
    submitting,
    loadingNext,
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
