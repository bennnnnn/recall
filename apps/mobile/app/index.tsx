import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  useWindowDimensions,
} from "react-native";
import { registerNewChat } from "@/lib/drawer";
import { Redirect, useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Ionicons } from "@expo/vector-icons";

import { useTheme } from "@/lib/theme";
import { ChatScreenBody } from "@/components/chat/ChatScreenBody";
import { ChatScreenMenuSheets } from "@/components/chat/ChatScreenMenuSheets";
import { makeChatScreenStyles } from "@/components/chat/chatScreenStyles";
import {
  COMPOSER_HEIGHT,
  composerAttachmentExtra,
} from "@/components/chat/ChatComposer";
import { DrawerShell } from "@/components/DrawerShell";
import { useAuth } from "@/contexts/AuthContext";
import { useProjects } from "@/contexts/ProjectsContext";
import { useDrawer } from "@/contexts/DrawerContext";
import { useHome } from "@/contexts/HomeContext";
import { useChat } from "@/hooks/useChat";
import { useChatActions } from "@/hooks/useChatActions";
import { useChatComposerState } from "@/hooks/useChatComposerState";
import { useChatDraftWarmup } from "@/hooks/useChatDraftWarmup";
import { useChatLayoutMetrics } from "@/hooks/useChatLayoutMetrics";
import { useChatMessageList } from "@/hooks/useChatMessageList";
import { useChatQuizContext } from "@/hooks/useChatQuizContext";
import { useChatRegenerate } from "@/hooks/useChatRegenerate";
import { useChatRouteLoader, useQueuedChatLaunch } from "@/hooks/useChatRouteLoader";
import { useChatScroll } from "@/hooks/useChatScroll";
import { useChatSend } from "@/hooks/useChatSend";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { useDraftChat } from "@/hooks/useDraftChat";
import { useDailyQuiz, appendQuizFeedbackMessage } from "@/hooks/useDailyQuiz";
import {
  buildDailyQuizLoadingMessage,
  buildDailyQuizMessage,
  buildDailyQuizErrorMessage,
  buildDailyQuizEmptyMessage,
  buildDailyQuizDoneMessage,
  dailyQuizMessageId,
  DAILY_QUIZ_DONE_ID,
  DAILY_QUIZ_LOADING_ID,
  isDailyQuizStatusMessageId,
  parseDailyQuizLetterReply,
} from "@/lib/dailyQuizMessage";
import { useModels } from "@/hooks/useModels";
import { useNetwork } from "@/contexts/NetworkContext";
import { useChatErrorHandlers, useChatStreamLifecycle } from "@/hooks/useChatScreenError";
import { useChatScreenBodyProps } from "@/hooks/useChatScreenBodyProps";
import { useReminderBadgeCount } from "@/hooks/useReminderBadgeCount";
import { useTodosOptional } from "@/contexts/TodosContext";
import { isComposerMenuOverlayOpen, CHAT_COMPOSER_MIN_BOTTOM_PAD } from "@/lib/chatComposerLogic";
import { useKeyboardInset } from "@/hooks/useKeyboardInset";

function ChatScreen() {
  const { token, user, mergeUser } = useAuth();
  const { projects } = useProjects();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeChatScreenStyles(C), [C]);
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { height: windowHeight } = useWindowDimensions();
  const drawerOpen = useDrawer().isOpen;
  const { chatId: routeChatId, prompt: routePrompt, launchId: routeLaunchId, highlightMessage: routeHighlightMessage } =
    useLocalSearchParams<{ chatId?: string; prompt?: string; launchId?: string; highlightMessage?: string }>();

  const [chatId, setChatId] = useState<string | null>(null);
  const draft = useDraftChat({ token, chatId });
  const {
    quizLanguage,
    setQuizLanguage,
    quizVariant,
    setQuizVariant,
    resolveQuizVariant,
    resolveQuizProjectId,
  } = useChatQuizContext({
    projects,
    draftProjectIdRef: draft.draftProjectIdRef,
  });
  const { isPro, autoEnabled, modelEnabledSet, AUTO_MODEL_ID } = useModels();
  const { unseenCount, showIndicator } = useReminderBadgeCount({ enabled: Boolean(token) });
  const { refresh: refreshHome } = useHome();
  const { chatError, handleChatError, handleStreamBusy, dismissChatError } =
    useChatErrorHandlers(isPro);
  const activeChatId = draft.activeChatId;

  const onFirstReplyRef = useRef<() => Promise<void>>(async () => {});
  const setInputRef = useRef<(value: string) => void>(() => {});
  const closeAttachSheetRef = useRef<() => void>(() => {});
  const showActionBannerRef = useRef<
    (message: string, icon?: keyof typeof Ionicons.glyphMap) => void
  >(() => {});

  const todosCtx = useTodosOptional();
  const handleTodosSync = useCallback(() => {
    void todosCtx?.refresh({ silent: true, force: true });
  }, [todosCtx]);

  const {
    messages,
    setMessages,
    streaming,
    finalizing,
    sendingMessageId,
    sendMessage,
    regenerateResponse,
    editMessage,
    stopGeneration,
    connect,
  } = useChat(token, activeChatId, {
    onFirstReply: () => onFirstReplyRef.current(),
    onError: handleChatError,
    onTodosSync: handleTodosSync,
  });

  const streamActive = streaming || finalizing;

  const quotaNudge = useChatStreamLifecycle({
    streamActive,
    dismissChatError,
    refreshHome,
    token,
    isPro,
  });

  const idleComposerBottomPad = Math.max(insets.bottom, CHAT_COMPOSER_MIN_BOTTOM_PAD);
  const { keyboardHeight, composerAnimatedStyle } = useKeyboardInset({
    idleBottomPad: idleComposerBottomPad,
  });

  const scroll = useChatScroll({
    chatId,
    messagesLength: messages.length,
    streamActive,
    windowHeight,
    keyboardHeight,
  });

  const routeLoader = useChatRouteLoader({
    token,
    routeChatId: typeof routeChatId === "string" ? routeChatId : undefined,
    routeHighlightMessage:
      typeof routeHighlightMessage === "string" ? routeHighlightMessage : undefined,
    routePrompt: typeof routePrompt === "string" ? routePrompt : undefined,
    routeLaunchId: typeof routeLaunchId === "string" ? routeLaunchId : undefined,
    router,
    draft,
    chatId,
    setChatId,
    setMessages,
    messages,
    streaming: streamActive,
    stopGeneration,
    setQuizLanguage,
    setQuizVariant,
    resolveQuizVariant,
    setInputRef,
    listRef: scroll.listRef,
    showActionBanner: (message, icon) => showActionBannerRef.current(message, icon),
    t,
  });

  onFirstReplyRef.current = routeLoader.handleFirstReply;
  useQueuedChatLaunch(token, routeLoader.beginChatLaunch);

  const {
    chatTitle,
    setChatTitle,
    titleGenerating,
    pinned,
    setPinned,
    chatLoading,
    hasMoreOlder,
    loadingOlder,
    loadOlderMessages,
    highlightedMessageId,
    startNewChat,
    pendingLaunch,
    setPendingLaunch,
    pendingLaunchRef,
    dailyQuizActive,
    dailyQuizProjectId,
    releaseDailyQuizPanel,
  } = routeLoader;

  const dailyQuizHandoffRef = useRef(false);
  const displayedQuestionIdsRef = useRef(new Set<string>());

  const handleQuizFeedback = useCallback(
    (feedback: string) => {
      appendQuizFeedbackMessage(setMessages, feedback);
      scroll.scrollToLatest();
    },
    [setMessages, scroll],
  );

  const handleQuizProgress = useCallback(
    (answered: number, goal: number) => {
      if (answered >= goal) {
        void refreshHome();
      }
    },
    [refreshHome],
  );

  const handleSuggestMcq = useCallback(() => {
    handleQuizFeedback(t("daily_quiz.switch_to_mcq"));
  }, [handleQuizFeedback, t]);

  const dailyQuiz = useDailyQuiz({
    token,
    projectId: dailyQuizProjectId,
    chatId: activeChatId,
    enabled: dailyQuizActive && Boolean(dailyQuizProjectId),
    onFeedback: handleQuizFeedback,
    onProgress: handleQuizProgress,
    onSuggestMcq: handleSuggestMcq,
  });

  useEffect(() => {
    if (!dailyQuizActive) return;
    scroll.scrollToLatest();
  }, [dailyQuizActive, dailyQuiz.session?.current?.id, scroll]);

  useEffect(() => {
    if (!dailyQuizActive || !dailyQuiz.submitting) return;
    scroll.scrollToLatest();
  }, [dailyQuizActive, dailyQuiz.submitting, scroll]);

  useEffect(() => {
    if (!dailyQuizActive) {
      displayedQuestionIdsRef.current.clear();
      dailyQuizHandoffRef.current = false;
      return;
    }
    if (dailyQuiz.loading) return;
    if (dailyQuizHandoffRef.current) return;

    if (dailyQuiz.error) {
      setMessages([buildDailyQuizErrorMessage(t("daily_quiz.error"))]);
      return;
    }

    const session = dailyQuiz.session;
    if (!session) {
      setMessages([buildDailyQuizEmptyMessage(t("daily_quiz.empty"))]);
      return;
    }

    if (session.complete && session.answered_count >= session.daily_goal) {
      setMessages((prev) => {
        const withoutStatus = prev.filter((m) => !isDailyQuizStatusMessageId(m.id));
        const withoutQuestions = withoutStatus.filter(
          (m) => !m.id.startsWith("daily-quiz-") || m.id === DAILY_QUIZ_DONE_ID,
        );
        if (withoutQuestions.some((m) => m.id === DAILY_QUIZ_DONE_ID)) {
          return withoutQuestions;
        }
        return [...withoutQuestions, buildDailyQuizDoneMessage(t("daily_quiz.done_body"))];
      });
      void refreshHome();
      return;
    }

    if (!session.current) {
      if (dailyQuiz.loadingNext) {
        setMessages((prev) => {
          const withoutStatus = prev.filter((m) => !isDailyQuizStatusMessageId(m.id));
          if (withoutStatus.some((m) => m.id === DAILY_QUIZ_LOADING_ID)) {
            return withoutStatus;
          }
          return [...withoutStatus, buildDailyQuizLoadingMessage()];
        });
        return;
      }
      setMessages([buildDailyQuizEmptyMessage(t("daily_quiz.empty"))]);
      return;
    }

    const question = session.current;
    setMessages((prev) => {
      const withoutStatus = prev.filter((m) => !isDailyQuizStatusMessageId(m.id));
      const msgId = dailyQuizMessageId(question.id);
      const nextMsg = buildDailyQuizMessage(question, session, dailyQuiz.modality);
      const existing = withoutStatus.find((m) => m.id === msgId);
      if (existing) {
        if (existing.content === nextMsg.content) return withoutStatus;
        return withoutStatus.map((m) => (m.id === msgId ? nextMsg : m));
      }
      displayedQuestionIdsRef.current.add(question.id);
      return [...withoutStatus, nextMsg];
    });
  }, [
    dailyQuizActive,
    dailyQuiz.session,
    dailyQuiz.session?.current?.id,
    dailyQuiz.session?.complete,
    dailyQuiz.modality,
    dailyQuiz.loading,
    dailyQuiz.loadingNext,
    dailyQuiz.error,
    setMessages,
    t,
    refreshHome,
  ]);

  useEffect(() => {
    if (!dailyQuizActive || !dailyQuizProjectId || chatTitle) return;
    const project = projects.find((p) => p.id === dailyQuizProjectId);
    if (project?.title) {
      setChatTitle(project.title);
    }
  }, [dailyQuizActive, dailyQuizProjectId, chatTitle, projects, setChatTitle]);

  const chatActions = useChatActions({
    token,
    chatId,
    chatTitle,
    messages,
    pinned,
    setPinned,
    setChatTitle,
    setMessages,
    router,
    t,
  });

  showActionBannerRef.current = chatActions.showActionBanner;

  const {
    menuVisible,
    setMenuVisible,
    renameVisible,
    renameText,
    setRenameText,
    setRenameVisible,
    actionBanner,
    dismissActionBanner,
    handleFeedback,
    confirmRename,
    onShareFromMenu,
    onRenameFromMenu,
    onTogglePinFromMenu,
    onDeleteFromMenu,
  } = chatActions;

  const composer = useChatComposerState({
    autoEnabled,
    modelEnabledSet,
    autoModelId: AUTO_MODEL_ID,
  });

  const { selectedModel } = composer;
  const { isOffline } = useNetwork();

  const handleDailyQuizBeforeSend = useCallback(
    (text: string): boolean => {
      if (!dailyQuizActive) return false;

      const session = dailyQuiz.session;
      const question = session?.current;
      const letter = parseDailyQuizLetterReply(text);

      if (dailyQuiz.loading || dailyQuiz.submitting || dailyQuiz.loadingNext) {
        setInputRef.current("");
        return true;
      }

      if (letter && session && session.complete && session.answered_count >= session.daily_goal) {
        setInputRef.current("");
        return true;
      }

      if (question && session && !session.complete) {
        if (letter) {
          const pickId = `local-quiz-pick-${question.id}`;
          setMessages((prev) => {
            const withoutOld = prev.filter((m) => m.id !== pickId);
            return [
              ...withoutOld,
              {
                id: pickId,
                role: "user",
                content: letter,
                model: null,
                created_at: new Date().toISOString(),
              },
            ];
          });
          scroll.scrollToLatest();
          setInputRef.current("");
          void dailyQuiz.submitAnswer(question, { modality: "mcq", letter });
          return true;
        }
        handleQuizFeedback(t("daily_quiz.reply_with_letter"));
        setInputRef.current("");
        return true;
      }

      if (session && !session.complete && !question) {
        setInputRef.current("");
        return true;
      }

      dailyQuizHandoffRef.current = true;
      releaseDailyQuizPanel();
      if (!/quiz|question|bonus|more/i.test(text) || quizVariant !== "trivia") return false;
      setMessages((prev) => prev.filter((m) => !isDailyQuizStatusMessageId(m.id)));
      return false;
    },
    [
      dailyQuizActive,
      dailyQuiz.session,
      dailyQuiz.loading,
      dailyQuiz.loadingNext,
      dailyQuiz.submitting,
      dailyQuiz,
      handleQuizFeedback,
      releaseDailyQuizPanel,
      quizVariant,
      setMessages,
      scroll,
      t,
    ],
  );

  const send = useChatSend({
    token,
    chatId,
    setChatId,
    setChatTitle,
    router,
    draft,
    scroll,
    streaming: streamActive,
    sendMessage,
    editMessage,
    setMessages,
    selectedModel,
    pendingLaunch,
    setPendingLaunch,
    pendingLaunchRef,
    user,
    mergeUser,
    t,
    onStreamBusy: handleStreamBusy,
    isOffline,
    resolveQuizProjectId,
    onBeforeSend: handleDailyQuizBeforeSend,
  });

  const {
    input,
    setInput,
    pendingAttachment,
    setPendingAttachment,
    attachBusy,
    attachSheetOpen,
    setAttachSheetOpen,
    editingMessageId,
    setEditingMessageId,
    handleSend,
    handlePickAttachment,
    handleAttachmentSheetSelect,
    handleEditMessage,
    creatingRef,
    pendingOutboundId,
  } = send;

  const {
    voiceInputAvailable,
    voiceRecording,
    voiceTranscribing,
    voiceMeterLevel,
    toggleVoiceInput,
  } = useVoiceInput({
    token,
    onTranscript: (text) => {
      setInput((prev) => (prev.trim() ? `${prev.trim()} ${text}` : text));
    },
    t,
  });

  closeAttachSheetRef.current = () => setAttachSheetOpen(false);

  const closeAttachSheet = useCallback(() => {
    setAttachSheetOpen(false);
  }, []);

  setInputRef.current = setInput;

  useEffect(() => {
    registerNewChat(startNewChat);
  }, [startNewChat]);

  const {
    listRef,
    listBottomPadRef,
    showScrollToBottom,
    scrollAwayCount,
    scrollToLatest,
    handleScroll,
    handleScrollEnd,
  } = scroll;

  const { prepareDraftChat, draftChatId } = draft;

  useChatDraftWarmup({
    token,
    routeChatId: typeof routeChatId === "string" ? routeChatId : undefined,
    chatId,
    messagesLength: messages.length,
    streaming: streamActive,
    draftChatId,
    prepareDraftChat,
    connect,
  });

  const handleRegenerate = useChatRegenerate({
    token,
    messages,
    mergeUser,
    regenerateResponse,
  });

  const displayMessages = useMemo(() => {
    if (!dailyQuizActive) return messages;
    if (!dailyQuiz.error && !dailyQuiz.session && (dailyQuiz.loading || messages.length === 0)) {
      return [buildDailyQuizLoadingMessage()];
    }
    if ((dailyQuiz.loading || dailyQuiz.loadingNext) && messages.length === 0) {
      return [buildDailyQuizLoadingMessage()];
    }
    if (dailyQuiz.submitting && !messages.some((m) => m.id === DAILY_QUIZ_LOADING_ID)) {
      return [...messages, buildDailyQuizLoadingMessage()];
    }
    return messages;
  }, [
    messages,
    dailyQuizActive,
    dailyQuiz.loading,
    dailyQuiz.loadingNext,
    dailyQuiz.submitting,
    dailyQuiz.session,
    dailyQuiz.error,
  ]);

  const { headerTitleLabel, renderItem } = useChatMessageList({
    messages: displayMessages,
    streaming,
    finalizing,
    selectedModel,
    quizLanguage,
    quizVariant,
    highlightedMessageId,
    sendingMessageId: sendingMessageId ?? pendingOutboundId,
    setMenuVisible,
    regenerateResponse: handleRegenerate,
    handleEditMessage,
    handleFeedback,
  });

  const layout = useChatLayoutMetrics({
    insetsTop: insets.top,
    insetsBottom: insets.bottom,
    windowHeight,
    keyboardHeight,
    composerHeight: COMPOSER_HEIGHT,
    attachmentExtra: composerAttachmentExtra(pendingAttachment),
    messagesLength: displayMessages.length,
    streaming: streamActive,
  });

  const menuOverlayOpen = isComposerMenuOverlayOpen(attachSheetOpen);

  const chatScreenBodyProps = useChatScreenBodyProps({
    styles: s,
    theme: C,
    token: token ?? "",
    drawerOpen,
    insetsTop: insets.top,
    router,
    routeChatId: typeof routeChatId === "string" ? routeChatId : undefined,
    layout,
    listBottomPadRef,
    actionBanner,
    dismissActionBanner,
    listRef,
    messages: displayMessages,
    hasMoreOlder,
    loadingOlder,
    chatLoading,
    renderItem,
    loadOlderMessages,
    handleScroll,
    handleScrollEnd,
    handleSend,
    headerTitleLabel,
    titleGenerating,
    chatTitle,
    showIndicator,
    unseenCount,
    startNewChat,
    setMenuVisible,
    menuOverlayOpen,
    showScrollToBottom,
    scrollAwayCount,
    scrollToLatest,
    attachSheetOpen,
    closeAttachSheet,
    quotaNudge,
    chatError,
    isPro,
    dismissChatError,
    composerAnimatedStyle,
    input,
    setInput,
    streaming,
    attachBusy,
    pendingAttachment,
    setPendingAttachment,
    editingMessageId,
    setEditingMessageId,
    handlePickAttachment,
    handleAttachmentSheetSelect,
    stopGeneration,
    isOffline,
    voiceRecording,
    voiceTranscribing,
    voiceMeterLevel,
    toggleVoiceInput,
    hideHomeStarters: dailyQuizActive,
  });

  if (!token) return <Redirect href="/login" />;

  return (
    <>
      <ChatScreenMenuSheets
        menuVisible={menuVisible}
        chatTitle={chatTitle}
        pinned={pinned}
        onCloseMenu={() => setMenuVisible(false)}
        onShare={onShareFromMenu}
        onRename={onRenameFromMenu}
        onTogglePin={onTogglePinFromMenu}
        onDelete={onDeleteFromMenu}
        renameVisible={renameVisible}
        renameText={renameText}
        onRenameTextChange={setRenameText}
        onCloseRename={() => setRenameVisible(false)}
        onConfirmRename={() => void confirmRename()}
      />

      <ChatScreenBody {...chatScreenBodyProps} />
    </>
  );
}

export default function HomeScreen() {
  return (
    <DrawerShell>
      <ChatScreen />
    </DrawerShell>
  );
}
