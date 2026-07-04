import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";
import { Redirect, Stack, useLocalSearchParams, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { VocabQuizChoices } from "@/components/VocabQuizChoices";
import { MarkdownContent } from "@/components/MarkdownContent";
import { useAuth } from "@/contexts/AuthContext";
import { useChat } from "@/hooks/useChat";
import { api, type ProjectDetail } from "@/lib/api";
import { queueChatLaunch } from "@/lib/chatLaunch";
import {
  buildProjectChatTutorPrompt,
  buildProjectExamBonusPrompt,
  buildProjectExamPrompt,
  isDailyGoalMet,
  resolveProjectDailyGoal,
} from "@/lib/projectChat";
import {
  cleanQuizWord,
  inferQuizAnswersFromMessages,
  isCompleteVocabQuiz,
  parseVocabQuiz,
  stripVocabQuizBlock,
  type QuizAnswerMeta,
} from "@/lib/parseVocabQuiz";
import { quizVariantForProjectKind } from "@/lib/quizVariant";
import { Theme, useTheme } from "@/lib/theme";

export default function ProjectExamQuizScreen() {
  const { token } = useAuth();
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [chatId, setChatId] = useState<string | null>(null);
  const startedRef = useRef(false);

  const { messages, streaming, sendMessage } = useChat(token, chatId, {
    onError: () => {},
  });

  const hasAssistantReply = useMemo(
    () => messages.some((m) => m.role === "assistant" && m.id !== "streaming"),
    [messages],
  );

  const quizVariant =
    project != null ? quizVariantForProjectKind(project.kind) : ("vocab" as const);

  const quizAnswers = useMemo(
    () => inferQuizAnswersFromMessages(messages),
    [messages],
  );

  const activeQuiz = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const msg = messages[i];
      if (msg.role !== "assistant") continue;
      const parsed = parseVocabQuiz(msg.content);
      if (isCompleteVocabQuiz(parsed)) {
        return { message: msg, quiz: parsed };
      }
    }
    return null;
  }, [messages]);

  const feedbackMarkdown = useMemo(() => {
    if (!activeQuiz) return "";
    const answered = quizAnswers[activeQuiz.message.id];
    if (!answered) return "";
    return stripVocabQuizBlock(activeQuiz.message.content).trim();
  }, [activeQuiz, quizAnswers]);

  useEffect(() => {
    if (!token || typeof id !== "string") return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const detail = await api.getProject(token, id);
        if (cancelled) return;
        setProject(detail);
        const chat = await api.createChat(token, "auto", id, "exam");
        if (cancelled) return;
        setChatId(chat.id);
      } catch {
        if (!cancelled) router.back();
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, id, router]);

  useEffect(() => {
    if (!project || !chatId || startedRef.current || streaming) return;
    if (isDailyGoalMet(project)) return;
    startedRef.current = true;
    sendMessage(buildProjectExamPrompt(project));
  }, [project, chatId, streaming, sendMessage]);

  const requestBonusQuestion = useCallback(() => {
    if (!project || streaming) return;
    sendMessage(buildProjectExamBonusPrompt(project));
  }, [project, streaming, sendMessage]);

  const retryQuestion = useCallback(() => {
    if (!project || streaming) return;
    sendMessage(
      "Send the next multiple-choice question using vocab_quiz JSON only. One question — wait for my A–D answer.",
    );
  }, [project, streaming, sendMessage]);

  const handleQuizAnswer = useCallback(
    (messageId: string, letter: "A" | "B" | "C" | "D", meta?: QuizAnswerMeta) => {
      if (streaming || !token || !project || !chatId) return;
      sendMessage(letter);
      if (/^[0-9a-f-]{36}$/i.test(messageId)) {
        void api
          .recordProjectQuizAnswer(token, project.id, {
            chat_id: chatId,
            assistant_message_id: messageId,
            letter,
            ...(meta?.topic ? { topic: meta.topic } : {}),
            ...(meta?.question ? { question: meta.question } : {}),
            ...(meta?.isCorrect != null ? { is_correct: meta.isCorrect } : {}),
          })
          .then(() => api.getProject(token, project.id))
          .then((detail) => {
            setProject(detail);
          })
          .catch(() => {});
      }
    },
    [streaming, token, project, chatId, sendMessage],
  );

  if (!token) return <Redirect href="/login" />;
  if (loading || !project) {
    return (
      <View style={s.center}>
        <ActivityIndicator color={theme.primary} />
      </View>
    );
  }

  const dailyGoal = resolveProjectDailyGoal(project);
  const masteredToday = project.stats.mastered_today;
  const goalMet = isDailyGoalMet(project);
  const goalDoneHint = t("projects.quiz.exam_goal_done_hint");
  const showRetry = !activeQuiz && !streaming && hasAssistantReply;
  const showGoalDone = goalMet && !activeQuiz && !streaming && !hasAssistantReply;
  const showLoading =
    !activeQuiz && !showGoalDone && !showRetry && (streaming || (!goalMet && !hasAssistantReply));

  return (
    <SafeAreaView style={s.root} edges={["top", "bottom"]}>
      <Stack.Screen options={{ title: t("projects.quiz.exam_title") }} />
      <View style={s.header}>
        <Text style={s.progress}>
          {t("projects.quiz.exam_progress", {
            done: masteredToday,
            goal: dailyGoal,
          })}
        </Text>
        {goalMet ? <Text style={s.goalDone}>{goalDoneHint}</Text> : null}
      </View>

      <View style={s.body}>
        {activeQuiz ? (
          <>
            {feedbackMarkdown ? (
              <View style={s.feedback}>
                <MarkdownContent content={feedbackMarkdown} />
              </View>
            ) : null}
            <VocabQuizChoices
              quiz={activeQuiz.quiz}
              variant={quizVariant}
              disabled={streaming || quizAnswers[activeQuiz.message.id] != null}
              language="en"
              initialSelected={quizAnswers[activeQuiz.message.id] ?? null}
              onSelect={(letter) => {
                const quiz = activeQuiz.quiz;
                const isCorrect = quiz.correct != null ? letter === quiz.correct : null;
                handleQuizAnswer(activeQuiz.message.id, letter, {
                  topic: cleanQuizWord(quiz.word),
                  question:
                    quizVariant === "trivia"
                      ? quiz.question?.trim() || cleanQuizWord(quiz.word)
                      : quiz.question?.trim() || "",
                  isCorrect,
                });
              }}
            />
          </>
        ) : showGoalDone ? (
          <View style={s.center}>
            <Ionicons name="checkmark-circle" size={48} color={theme.primary} />
            <Text style={s.doneTitle}>{t("projects.quiz.exam_done_title")}</Text>
            <Text style={s.doneBody}>{t("projects.quiz.exam_done_body")}</Text>
            <Pressable style={s.bonusBtn} onPress={requestBonusQuestion}>
              <Text style={s.bonusBtnText}>{t("projects.quiz.exam_bonus")}</Text>
            </Pressable>
          </View>
        ) : showLoading ? (
          <View style={s.center}>
            <ActivityIndicator color={theme.primary} />
            <Text style={s.waiting}>{t("projects.quiz.exam_loading")}</Text>
          </View>
        ) : showRetry ? (
          <View style={s.center}>
            <Text style={s.waiting}>{t("projects.quiz.exam_retry_hint")}</Text>
            <Pressable style={s.bonusBtn} onPress={retryQuestion}>
              <Text style={s.bonusBtnText}>{t("projects.quiz.exam_retry")}</Text>
            </Pressable>
          </View>
        ) : null}
      </View>

      <View style={s.footer}>
        <Pressable
          style={s.chatLink}
          onPress={() => {
            queueChatLaunch(
              buildProjectChatTutorPrompt(project),
              project.id,
              quizVariant === "vocab" ? "en" : undefined,
              quizVariant,
              "chat",
            );
            router.replace("/");
          }}
        >
          <Ionicons name="chatbubble-outline" size={18} color={theme.primary} />
          <Text style={s.chatLinkText}>{t("projects.quiz.switch_to_chat")}</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: t.bg },
    center: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12 },
    header: {
      paddingHorizontal: 20,
      paddingVertical: 12,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
      gap: 4,
    },
    progress: { fontSize: 16, fontWeight: "600", color: t.text },
    goalDone: { fontSize: 14, color: t.textSecondary },
    body: { flex: 1, padding: 16, justifyContent: "center" },
    feedback: { marginBottom: 12 },
    waiting: { color: t.textSecondary, fontSize: 15, textAlign: "center", paddingHorizontal: 24 },
    doneTitle: { fontSize: 20, fontWeight: "700", color: t.text },
    doneBody: {
      fontSize: 15,
      lineHeight: 22,
      color: t.textSecondary,
      textAlign: "center",
      paddingHorizontal: 24,
    },
    bonusBtn: {
      marginTop: 8,
      paddingHorizontal: 18,
      paddingVertical: 12,
      borderRadius: 12,
      backgroundColor: t.primaryLight,
    },
    bonusBtnText: { fontSize: 15, fontWeight: "700", color: t.primary },
    footer: {
      padding: 16,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.border,
      alignItems: "center",
    },
    chatLink: { flexDirection: "row", alignItems: "center", gap: 6 },
    chatLinkText: { color: t.primary, fontSize: 15, fontWeight: "500" },
  });
}
