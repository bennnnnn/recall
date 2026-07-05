import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
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
  dailyQuizMessageId,
  isDailyQuizMessageId,
  questionIdFromDailyQuizMessageId,
} from "@/lib/dailyQuizMessage";
import { getQuizUiStyle, setQuizUiStyle, type QuizUiStyle } from "@/lib/quizUiPrefs";
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
  const { isPro, labelFor, autoEnabled, modelEnabledSet, AUTO_MODEL_ID, models } = useModels();
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
  } = routeLoader;

  const dailyQuizProjectId = dailyQuizActive ? resolveQuizProjectId() : null;
  const [quizUiStyle, setQuizUiStyleState] = useState<QuizUiStyle>("card");
  const quizUiPrefPromptedRef = useRef(false);
  const displayedQuestionIdsRef = useRef(new Set<string>());

  useEffect(() => {
    if (!dailyQuizActive) return;
    void getQuizUiStyle().then((style) => {
      if (style) setQuizUiStyleState(style);
    });
  }, [dailyQuizActive]);

  const handleQuizFeedback = useCallback(
    (feedback: string) => {
      appendQuizFeedbackMessage(setMessages, feedback);
      scroll.scrollToLatest();
    },
    [setMessages, scroll],
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
    onSuggestMcq: handleSuggestMcq,
  });

  useEffect(() => {
    const currentId = dailyQuiz.session?.current?.id;
    if (!dailyQuizActive || !currentId || quizUiPrefPromptedRef.current) return;
    quizUiPrefPromptedRef.current = true;
    void (async () => {
      const existing = await getQuizUiStyle();
      if (existing) {
        setQuizUiStyleState(existing);
        return;
      }
      Alert.alert(
        t("daily_quiz.ui_pref_title"),
        t("daily_quiz.ui_pref_body"),
        [
          {
            text: t("daily_quiz.ui_pref_card"),
            onPress: () => {
              void setQuizUiStyle("card");
              setQuizUiStyleState("card");
            },
          },
          {
            text: t("daily_quiz.ui_pref_simple"),
            onPress: () => {
              void setQuizUiStyle("simple");
              setQuizUiStyleState("simple");
            },
          },
        ],
        { cancelable: false },
      );
    })();
  }, [dailyQuizActive, dailyQuiz.session?.current?.id, t]);

  useEffect(() => {
    if (!dailyQuizActive) return;
    scroll.scrollToLatest();
  }, [dailyQuizActive, dailyQuiz.session?.current?.id, scroll]);

  useEffect(() => {
    if (!dailyQuizActive) {
      displayedQuestionIdsRef.current.clear();
      return;
    }
    const session = dailyQuiz.session;
    const question = session?.current;
    if (!question || dailyQuiz.loading) return;

    setMessages((prev) => {
      const msgId = dailyQuizMessageId(question.id);
      const nextMsg = buildDailyQuizMessage(question, session, dailyQuiz.modality);
      const existing = prev.find((m) => m.id === msgId);
      if (existing) {
        if (existing.content === nextMsg.content) return prev;
        return prev.map((m) => (m.id === msgId ? nextMsg : m));
      }
      displayedQuestionIdsRef.current.add(question.id);
      return [...prev, nextMsg];
    });
  }, [
    dailyQuizActive,
    dailyQuiz.session,
    dailyQuiz.session?.current?.id,
    dailyQuiz.modality,
    dailyQuiz.loading,
    setMessages,
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
    models,
    isPro,
    labelFor,
    autoModelId: AUTO_MODEL_ID,
    t,
    closeAttachSheetRef,
  });

  const { selectedModel, ...composerUi } = composer;
  const { isOffline } = useNetwork();

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
    handleQuizAnswer,
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

  const {
    showModelPicker,
    modelOptions,
    selectedModelLabel,
    closePickers: closeComposerPickers,
    toggleModelPicker,
    selectModel,
  } = composerUi;

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
    if (dailyQuiz.loading && !dailyQuiz.session) {
      return [...messages, buildDailyQuizLoadingMessage()];
    }
    return messages;
  }, [messages, dailyQuizActive, dailyQuiz.loading, dailyQuiz.session]);

  const wrappedHandleQuizAnswer = useCallback(
    (
      messageId: string,
      letter: "A" | "B" | "C" | "D",
      meta?: import("@/lib/parseVocabQuiz").QuizAnswerMeta,
    ) => {
      if (isDailyQuizMessageId(messageId)) {
        const questionId = questionIdFromDailyQuizMessageId(messageId);
        const question = dailyQuiz.session?.current;
        if (question?.id === questionId && !dailyQuiz.submitting) {
          const pickId = `local-quiz-pick-${questionId}`;
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
          void dailyQuiz.submitAnswer(question, { modality: "mcq", letter });
        }
        return;
      }
      handleQuizAnswer(messageId, letter, meta);
    },
    [dailyQuiz, handleQuizAnswer, setMessages, scroll],
  );

  const dailyQuizRow = useMemo(
    () =>
      dailyQuizActive
        ? {
            active: true,
            submitting: dailyQuiz.submitting,
            allowRetry: dailyQuiz.allowRetry,
            currentQuestion: dailyQuiz.session?.current ?? null,
            onModalityChange: dailyQuiz.setModality,
            onTextAnswer: (
              question: import("@/lib/api").ProjectQuizQuestion,
              text: string,
              modality: "definition" | "sentence",
            ) => void dailyQuiz.submitAnswer(question, { modality, text }),
            onSkip: (question: import("@/lib/api").ProjectQuizQuestion) =>
              void dailyQuiz.skipQuestion(question),
          }
        : undefined,
    [dailyQuizActive, dailyQuiz],
  );

  const { headerTitleLabel, renderItem } = useChatMessageList({
    messages: displayMessages,
    streaming,
    finalizing,
    selectedModel,
    quizLanguage,
    quizVariant,
    highlightedMessageId,
    sendingMessageId: sendingMessageId ?? pendingOutboundId,
    creatingRef,
    setMenuVisible,
    regenerateResponse: handleRegenerate,
    handleEditMessage,
    handleFeedback,
    handleQuizAnswer: wrappedHandleQuizAnswer,
    dailyQuizRow,
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
    showModelPicker,
    attachSheetOpen,
    closeComposerPickers,
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
    modelOptions,
    selectedModel,
    selectedModelLabel,
    toggleModelPicker,
    selectModel,
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
