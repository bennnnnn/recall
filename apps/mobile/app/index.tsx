import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  useWindowDimensions,
  View,
} from "react-native";
import { registerNewChat, setActiveChatIdGlobal } from "@/lib/drawer";
import { Redirect, useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { type IoniconName } from "@/lib/icons";
import { useTheme } from "@/lib/theme";
import { ChatScreenBody } from "@/components/chat/ChatScreenBody";
import { ChatScreenMenuSheets } from "@/components/chat/ChatScreenMenuSheets";
import { LiveTalkOverlay } from "@/components/chat/LiveTalkOverlay";
import { makeChatScreenStyles } from "@/components/chat/chatScreenStyles";
import {
  COMPOSER_HEIGHT,
  composerAttachmentExtra,
} from "@/components/chat/ChatComposer";
import { DrawerShell } from "@/components/DrawerShell";
import { ComposerDraftProvider } from "@/contexts/ComposerDraftContext";
import { useAuth } from "@/contexts/AuthContext";
import { useProjects } from "@/contexts/ProjectsContext";
import { useDrawer } from "@/contexts/DrawerContext";
import { useHome } from "@/contexts/HomeContext";
import { shouldRefreshHomeOnChatFocus } from "@/lib/cache/contextRefresh";
import { useChat } from "@/hooks/useChat";
import { useChatActions } from "@/hooks/useChatActions";
import { useChatComposerState } from "@/hooks/useChatComposerState";
import { useChatDraftWarmup } from "@/hooks/useChatDraftWarmup";
import { useChatLayoutMetrics } from "@/hooks/useChatLayoutMetrics";
import { useChatMessageList } from "@/hooks/useChatMessageList";
import { useChatSuggestions } from "@/hooks/useChatSuggestions";
import { useChatQuizContext } from "@/hooks/useChatQuizContext";
import { useChatRegenerate } from "@/hooks/useChatRegenerate";
import { useChatRouteLoader, useQueuedChatLaunch } from "@/hooks/useChatRouteLoader";
import { useChatScroll } from "@/hooks/useChatScroll";
import { useChatSend } from "@/hooks/useChatSend";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { useLiveTalk } from "@/hooks/useLiveTalk";
import { useDraftChat } from "@/hooks/useDraftChat";
import { useModels } from "@/hooks/useModels";
import { useNetwork } from "@/contexts/NetworkContext";
import { useChatErrorHandlers, useChatStreamLifecycle } from "@/hooks/useChatScreenError";
import { useChatScreenBodyProps } from "@/hooks/useChatScreenBodyProps";
import { useReminderBadgeCount } from "@/hooks/useReminderBadgeCount";
import { useTodosOptional } from "@/contexts/TodosContext";
import { isComposerMenuOverlayOpen, CHAT_COMPOSER_MIN_BOTTOM_PAD } from "@/lib/chatComposerLogic";
import { invalidateProjectDetail } from "@/lib/cache/projectDetailCache";
import { openLearningLesson } from "@/lib/lessonLaunch";
import { useImageGeneration } from "@/hooks/useImageGeneration";
import { subjectFromImageGenUserMessage } from "@/lib/imageGenIntent";
import { useKeyboardInset } from "@/hooks/useKeyboardInset";

function ChatScreen() {
  const { token, user, updateUser } = useAuth();
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
  useFocusEffect(
    useCallback(() => {
      const openThread =
        (typeof routeChatId === "string" && routeChatId) || chatId;
      if (!shouldRefreshHomeOnChatFocus(Boolean(openThread))) return;
      void refreshHome({ silent: true });
    }, [refreshHome, routeChatId, chatId]),
  );
  const { chatError, handleChatError, handleStreamBusy, dismissChatError } =
    useChatErrorHandlers(isPro);
  const activeChatId = draft.activeChatId;

  const onFirstReplyRef = useRef<() => Promise<void>>(async () => {});
  const setInputRef = useRef<(value: string) => void>(() => {});
  const closeAttachSheetRef = useRef<() => void>(() => {});
  const showActionBannerRef = useRef<
    (message: string, icon?: IoniconName) => void
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
    beginRegenerateUi,
    cancelRegenerateUi,
    regenerateResponse,
    editMessage,
    stopGeneration,
    connect,
  } = useChat(token, activeChatId, {
    onFirstReply: () => onFirstReplyRef.current(),
    onError: handleChatError,
    onTodosSync: handleTodosSync,
  });

  const llmBusy = streaming || finalizing;
  const imageGeneratingRef = useRef(false);
  const stopTurnRef = useRef<() => void>(() => {});
  const stopTurn = useCallback(() => {
    stopTurnRef.current();
  }, []);

  const idleComposerBottomPad = Math.max(insets.bottom, CHAT_COMPOSER_MIN_BOTTOM_PAD);
  const { keyboardHeight, composerAnimatedStyle } = useKeyboardInset({
    idleBottomPad: idleComposerBottomPad,
  });

  const scroll = useChatScroll({
    chatId,
    messagesLength: messages.length,
    streamActive: llmBusy,
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
    streaming: llmBusy,
    imageGeneratingRef,
    stopGeneration: stopTurn,
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
    archived,
    setArchived,
    chatLoading,
    hasMoreOlder,
    loadingOlder,
    loadOlderMessages,
    highlightedMessageId,
    startNewChat,
    pendingLaunch,
    setPendingLaunch,
    pendingLaunchRef,
  } = routeLoader;

  const chatActions = useChatActions({
    token,
    chatId,
    chatTitle,
    messages,
    pinned,
    setPinned,
    archived,
    setArchived,
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
    onExportPdfFromMenu,
    onRenameFromMenu,
    onTogglePinFromMenu,
    onToggleArchiveFromMenu,
    onDeleteFromMenu,
  } = chatActions;

  const composer = useChatComposerState({
    autoEnabled,
    modelEnabledSet,
    autoModelId: AUTO_MODEL_ID,
  });

  const { selectedModel } = composer;
  const { isOffline } = useNetwork();

  const openUpgradeRef = useRef<(() => void) | null>(null);

  const notifyOfflineBlocked = useCallback(() => {
    showActionBannerRef.current(t("chat.offline_body"), "cloud-offline-outline");
  }, [t]);

  const imageGen = useImageGeneration({
    token,
    chatId,
    setChatId,
    setChatTitle,
    setMessages,
    draft,
    router,
    selectedModel,
    streaming: llmBusy,
    isPro,
    isOffline,
    onOpenUpgrade: () => openUpgradeRef.current?.(),
    onOfflineBlocked: notifyOfflineBlocked,
    onScrollToLatest: scroll.scrollToLatest,
    newMessageCountRef: scroll.newMessageCountRef,
    t,
  });
  imageGeneratingRef.current = imageGen.generating;
  stopTurnRef.current = () => {
    imageGen.cancel();
    stopGeneration();
    dismissChatError();
  };
  const streamActive = llmBusy || imageGen.generating;

  const { turnRefreshKey, ...quotaNudge } = useChatStreamLifecycle({
    streamActive,
    dismissChatError,
    token,
    isPro,
  });

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
    messages,
    selectedModel,
    pendingLaunch,
    setPendingLaunch,
    pendingLaunchRef,
    user,
    updateUser,
    t,
    onStreamBusy: handleStreamBusy,
    onOfflineBlocked: notifyOfflineBlocked,
    isOffline,
    resolveQuizProjectId,
    imageGenerating: imageGen.generating,
    onGenerateImage: (prompt, userMessage) => {
      void imageGen.submitPrompt({ prompt, userMessage, aspectRatio: null });
    },
  });

  const {
    setInput,
    pendingAttachment,
    setPendingAttachment,
    attachBusy,
    attachPicking,
    sendPhase,
    attachSheetOpen,
    setAttachSheetOpen,
    editingMessageId,
    setEditingMessageId,
    handleSend,
    handlePickAttachment,
    handleAttachmentSheetSelect,
    handleMathScanCaptured,
    handleEditMessage,
    mathScannerOpen,
    setMathScannerOpen,
    pendingOutboundId,
  } = send;

  const [mathChromeExtra, setMathChromeExtra] = useState(0);

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

  const liveTalk = useLiveTalk({
    token,
    isOffline,
    onUpgrade: () => openUpgradeRef.current?.(),
    t,
  });

  closeAttachSheetRef.current = () => setAttachSheetOpen(false);

  const closeAttachSheet = useCallback(() => {
    setAttachSheetOpen(false);
  }, []);

  const closeMathScanner = useCallback(() => {
    setMathScannerOpen(false);
  }, [setMathScannerOpen]);

  setInputRef.current = setInput;

  useEffect(() => {
    setActiveChatIdGlobal(chatId);
    return () => setActiveChatIdGlobal(null);
  }, [chatId]);

  useEffect(() => {
    registerNewChat((opts) => {
      dismissChatError();
      startNewChat(opts);
    });
    return () => registerNewChat(null);
  }, [startNewChat, dismissChatError]);

  const {
    listRef,
    listBottomPadRef,
    showScrollToBottom,
    scrollAwayCount,
    scrollToLatest,
    handleScroll,
    handleScrollEnd,
  } = scroll;

  const { draftChatId } = draft;

  useChatDraftWarmup({
    token,
    chatId,
    streaming: streamActive,
    draftChatId,
    connect,
  });

  const { regenerate: handleRegenerate, regenerating } = useChatRegenerate({
    token,
    messages,
    user,
    updateUser,
    regenerateResponse,
    beginRegenerateUi,
    cancelRegenerateUi,
    regenerateImage: useCallback(
      (lastUserContent: string) => {
        const prompt = subjectFromImageGenUserMessage(lastUserContent);
        if (!prompt) return;
        void imageGen.submitPrompt({
          prompt,
          userMessage: lastUserContent,
          aspectRatio: null,
        });
      },
      [imageGen],
    ),
  });
  const retryChatError = useCallback(() => {
    if (streaming || finalizing || regenerating) return;
    dismissChatError();
    void handleRegenerate(selectedModel);
  }, [
    dismissChatError,
    finalizing,
    handleRegenerate,
    regenerating,
    selectedModel,
    streaming,
  ]);

  const displayMessages = messages;

  const { suggestions, dismiss: dismissSuggestion } = useChatSuggestions({
    token,
    hasMessages: displayMessages.length > 0,
    turnBusy: streamActive || Boolean(pendingOutboundId),
    refreshKey: turnRefreshKey,
  });

  const onSelectSuggestion = useCallback(
    (prompt: string) => {
      void handleSend(prompt);
    },
    [handleSend],
  );

  const onOpenLesson = useCallback(
    (projectId: string) => {
      if (!projectId) return;
      invalidateProjectDetail(projectId);
      openLearningLesson(router, { projectId });
    },
    [router],
  );

  const { headerTitleLabel, renderItem } = useChatMessageList({
    messages: displayMessages,
    streaming,
    finalizing,
    selectedModel,
    quizLanguage,
    highlightedMessageId,
    sendingMessageId: sendingMessageId ?? pendingOutboundId,
    setMenuVisible,
    regenerateResponse: handleRegenerate,
    regenerating,
    handleEditMessage,
    handleFeedback,
    suggestions,
    onSelectSuggestion,
    onDismissSuggestion: dismissSuggestion,
    imageGenerating: imageGen.generating,
    lessonProjectId: resolveQuizProjectId(),
    onOpenLesson,
    onRetryImageGen: imageGen.retry,
  });

  const layout = useChatLayoutMetrics({
    insetsTop: insets.top,
    insetsBottom: insets.bottom,
    windowHeight,
    keyboardHeight,
    composerHeight: COMPOSER_HEIGHT,
    attachmentExtra: composerAttachmentExtra(pendingAttachment),
    mathBarExtra: mathChromeExtra,
    messagesLength: displayMessages.length,
    streaming: streamActive,
    lastMessageId: displayMessages[displayMessages.length - 1]?.id,
  });

  const menuOverlayOpen = isComposerMenuOverlayOpen(attachSheetOpen);

  const chatScreenBody = useChatScreenBodyProps({
    styles: s,
    theme: C,
    token: token ?? "",
    drawerOpen,
    routeChatId: typeof routeChatId === "string" ? routeChatId : undefined,
    layout,
    listBottomPadRef,
    actionBanner,
    dismissActionBanner,
    header: {
      insetsTop: insets.top,
      router,
      headerTitleLabel,
      titleGenerating,
      chatTitle,
      showIndicator,
      unseenCount,
      startNewChat,
      setMenuVisible,
      menuOverlayOpen,
    },
    list: {
      listRef,
      messages: displayMessages,
      hasMoreOlder,
      loadingOlder,
      chatLoading,
      renderItem,
      loadOlderMessages,
      handleScroll,
      handleScrollEnd,
    },
    handleSend,
    showScrollToBottom,
    scrollAwayCount,
    scrollToLatest,
    attachments: {
      attachSheetOpen,
      closeAttachSheet,
      attachBusy,
      attachPicking,
      pendingAttachment,
      setPendingAttachment,
      handlePickAttachment,
      handleAttachmentSheetSelect,
      mathScannerOpen,
      closeMathScanner,
      handleMathScanCaptured,
      onOpenMathScanner: () => setMathScannerOpen(true),
      onMathChromeHeightChange: setMathChromeExtra,
    },
    quotaNudge,
    chatError,
    isPro,
    retryChatError,
    dismissChatError,
    composerAnimatedStyle,
    setInput,
    streaming: streamActive,
    sendBusy: sendPhase !== "idle",
    editing: { editingMessageId, setEditingMessageId },
    stopGeneration: stopTurn,
    isOffline,
    voice: {
      voiceAvailable: voiceInputAvailable,
      voiceRecording,
      voiceTranscribing,
      voiceMeterLevel,
      toggleVoiceInput,
      onLiveTalkPress: liveTalk.open,
    },
  });
  openUpgradeRef.current = chatScreenBody.openUpgradeSheet;
  const chatScreenBodyProps = chatScreenBody.bodyProps;

  if (!token) return <Redirect href="/login" />;

  return (
    <View style={{ flex: 1 }}>
      <ChatScreenBody {...chatScreenBodyProps} />
      <LiveTalkOverlay
        visible={liveTalk.visible}
        phase={liveTalk.phase}
        meterLevel={liveTalk.meterLevel}
        recording={liveTalk.recording}
        onClose={liveTalk.close}
        onToggle={() => void liveTalk.toggle()}
      />

      <ChatScreenMenuSheets
        menuVisible={menuVisible}
        chatTitle={chatTitle}
        pinned={pinned}
        archived={archived}
        onCloseMenu={() => setMenuVisible(false)}
        onShare={onShareFromMenu}
        onExportPdf={onExportPdfFromMenu}
        onRename={onRenameFromMenu}
        onTogglePin={onTogglePinFromMenu}
        onToggleArchive={onToggleArchiveFromMenu}
        onDelete={onDeleteFromMenu}
        renameVisible={renameVisible}
        renameText={renameText}
        onRenameTextChange={setRenameText}
        onCloseRename={() => setRenameVisible(false)}
        onConfirmRename={() => void confirmRename()}
      />
    </View>
  );
}

export default function HomeScreen() {
  return (
    <DrawerShell>
      <ComposerDraftProvider>
        <ChatScreen />
      </ComposerDraftProvider>
    </DrawerShell>
  );
}
