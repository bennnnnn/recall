import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  useWindowDimensions,
  View,
} from "react-native";
import { registerNewChat, setActiveChatIdGlobal } from "@/lib/drawer";
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
import { useChatSuggestions } from "@/hooks/useChatSuggestions";
import { useChatQuizContext } from "@/hooks/useChatQuizContext";
import { useChatRegenerate } from "@/hooks/useChatRegenerate";
import { useChatRouteLoader, useQueuedChatLaunch } from "@/hooks/useChatRouteLoader";
import { useChatScroll } from "@/hooks/useChatScroll";
import { useChatSend } from "@/hooks/useChatSend";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { useDraftChat } from "@/hooks/useDraftChat";
import { useModels } from "@/hooks/useModels";
import { useNetwork } from "@/contexts/NetworkContext";
import { useChatErrorHandlers, useChatStreamLifecycle } from "@/hooks/useChatScreenError";
import { useChatScreenBodyProps } from "@/hooks/useChatScreenBodyProps";
import { useReminderBadgeCount } from "@/hooks/useReminderBadgeCount";
import { useTodosOptional } from "@/contexts/TodosContext";
import { isComposerMenuOverlayOpen, CHAT_COMPOSER_MIN_BOTTOM_PAD } from "@/lib/chatComposerLogic";
import { invalidateProjectDetail } from "@/lib/projectDetailCache";
import { useImageGeneration } from "@/hooks/useImageGeneration";
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
    streaming: streamActive,
    isPro,
    isOffline,
    onOpenUpgrade: () => openUpgradeRef.current?.(),
    onOfflineBlocked: notifyOfflineBlocked,
    onScrollToLatest: scroll.scrollToLatest,
    newMessageCountRef: scroll.newMessageCountRef,
    t,
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
    onGenerateImage: (prompt) => {
      void imageGen.submitPrompt(prompt);
    },
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
    handleMathScanCaptured,
    handleEditMessage,
    mathScannerOpen,
    setMathScannerOpen,
    pendingOutboundId,
  } = send;

  const {
    voiceRecording,
    voiceTranscribing,
    voiceMeterLevel,
    toggleVoiceInput,
    cancelVoiceInput,
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
    user,
    updateUser,
    regenerateResponse,
  });

  const displayMessages = messages;

  const { suggestions, dismiss: dismissSuggestion } = useChatSuggestions({
    token,
    enabled: Boolean(token) && displayMessages.length > 0,
    refreshKey: `${streaming}-${finalizing}-${displayMessages.length}`,
  });

  const onSelectSuggestion = useCallback(
    (prompt: string) => {
      void handleSend(prompt);
    },
    [handleSend],
  );

  // Stable quiz-answer handler. An inline arrow here used to be recreated on
  // every ChatScreen render (including every composer keystroke) → it flowed
  // into useChatMessageList's sharedRowProps → renderItem → FlashList
  // re-rendered every row while typing. Memoize so the list stays stable.
  const onQuizAnswer = useCallback(
    (letter: string) => {
      // BUG FIX (was silent): answering a quiz in chat persists new counts server-side,
      // but nothing invalidated the project detail cache from this flow — returning to
      // the project screen right after could show a stale pre-answer snapshot for up
      // to the cache's 20s TTL. Bust it so the next detail fetch is fresh.
      const quizProjectId = resolveQuizProjectId();
      if (quizProjectId) invalidateProjectDetail(quizProjectId);
      void handleSend(letter);
    },
    [handleSend, resolveQuizProjectId],
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
    handleEditMessage,
    handleFeedback,
    suggestions,
    onSelectSuggestion,
    onDismissSuggestion: dismissSuggestion,
    imageGenerating: imageGen.generating,
    onQuizAnswer,
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
      pendingAttachment,
      setPendingAttachment,
      handlePickAttachment,
      handleAttachmentSheetSelect,
      mathScannerOpen,
      closeMathScanner,
      handleMathScanCaptured,
    },
    quotaNudge,
    chatError,
    isPro,
    dismissChatError,
    composerAnimatedStyle,
    input,
    setInput,
    streaming,
    editing: { editingMessageId, setEditingMessageId },
    stopGeneration,
    isOffline,
    voice: {
      voiceRecording,
      voiceTranscribing,
      voiceMeterLevel,
      toggleVoiceInput,
      cancelVoiceInput,
    },
  });
  openUpgradeRef.current = chatScreenBody.openUpgradeSheet;
  const chatScreenBodyProps = chatScreenBody.bodyProps;

  if (!token) return <Redirect href="/login" />;

  return (
    <View style={{ flex: 1 }}>
      <ChatScreenBody {...chatScreenBodyProps} />

      <ChatScreenMenuSheets
        menuVisible={menuVisible}
        chatTitle={chatTitle}
        pinned={pinned}
        archived={archived}
        onCloseMenu={() => setMenuVisible(false)}
        onShare={onShareFromMenu}
        onRename={onRenameFromMenu}
        onTogglePin={onTogglePinFromMenu}
        onToggleArchive={onToggleArchiveFromMenu}
        onDelete={onDeleteFromMenu}
        onOpenModels={() => {
          setMenuVisible(false);
          router.push("/settings/models");
        }}
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
      <ChatScreen />
    </DrawerShell>
  );
}
