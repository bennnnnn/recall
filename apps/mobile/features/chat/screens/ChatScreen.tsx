import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  useWindowDimensions,
  View,
} from "react-native";
import { registerNewChat, setActiveChatIdGlobal } from "@/features/chat/drawer/drawer";
import { Redirect, useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import type { IconName } from "@/ui/icons/names";
import { useTheme } from "@/lib/theme";
import { ChatScreenBody } from "@/features/chat/components/ChatScreenBody";
import { ChatScreenMenuSheets } from "@/features/chat/components/ChatScreenMenuSheets";
import { LazyLiveTalkOverlay } from "@/features/speech/components/LazyLiveTalkOverlay";
import { makeChatScreenStyles } from "@/features/chat/components/chatScreenStyles";
import { COMPOSER_HEIGHT } from "@/features/chat/components/ChatComposer";
import { composerAttachmentExtra } from "@/features/attachments/components/ComposerAttachmentPreview";
import { DrawerShell } from "@/features/chat/drawer/DrawerShell";
import { ComposerDraftProvider, useComposerDraftActivity } from "@/features/chat/context/ComposerDraftContext";
import { ChatReplyProviders } from "@/features/chat/components/ChatReplyProviders";
import { useAuth } from "@/contexts/AuthContext";
import type { UpgradeSource } from "@/components/UpgradeSheet";
import { useChat } from "@/features/chat/hooks/useChat";
import { useChatActions } from "@/features/chat/hooks/useChatActions";
import { useChatComposerState } from "@/features/chat/hooks/useChatComposerState";
import { useEnsureChatId } from "@/features/chat/hooks/useEnsureChatId";
import { useComposerDictation } from "@/features/chat/hooks/useComposerDictation";
import { useChatDraftWarmup } from "@/features/chat/hooks/useChatDraftWarmup";
import { useChatLayoutMetrics } from "@/features/chat/hooks/useChatLayoutMetrics";
import { useChatMessageList } from "@/features/chat/hooks/useChatMessageList";
import { useChatRegenerate } from "@/features/chat/hooks/useChatRegenerate";
import { useChatRouteLoader } from "@/features/chat/hooks/useChatRouteLoader";
import { useChatScroll, useScrollHoldForHighlight } from "@/features/chat/hooks/useChatScroll";
import { useChatSend } from "@/features/chat/hooks/useChatSend";
import { useLiveTalk } from "@/features/speech/hooks/useLiveTalk";
import { useDraftChat } from "@/features/chat/hooks/useDraftChat";
import { useModels } from "@/hooks/useModels";
import { useNetwork } from "@/contexts/NetworkContext";
import { useChatErrorHandlers, useChatErrorRecovery, useChatStreamLifecycle } from "@/features/chat/hooks/useChatScreenError";
import { useQuotaNudge } from "@/features/chat/hooks/useQuotaNudge";
import { useChatScreenBodyProps } from "@/features/chat/hooks/useChatScreenBodyProps";
import { useTodosOptional } from "@/features/todos/context/TodosContext";
import { isComposerMenuOverlayOpen, CHAT_COMPOSER_MIN_BOTTOM_PAD } from "@/features/chat/model/composerLogic";
import { useChatImageGeneration } from "@/features/chat/hooks/useChatImageGeneration";
import { useKeyboardInset } from "@/hooks/useKeyboardInset";

function ChatScreen() {
  const { token, user, updateUser } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeChatScreenStyles(C), [C]);
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { height: windowHeight, fontScale } = useWindowDimensions();
  const { chatId: routeChatId, highlightMessage: routeHighlightMessage } =
    useLocalSearchParams<{ chatId?: string; highlightMessage?: string }>();

  const [chatId, setChatId] = useState<string | null>(null);
  const composerActive = useComposerDraftActivity();
  const draft = useDraftChat({ chatId, intent: composerActive });
  const { isPaid, autoEnabled, modelEnabledSet, AUTO_MODEL_ID } = useModels();
  const {
    chatError, handleChatError, handleStreamBusy, dismissChatError, dismissBusyNotice, handleRejectedSendChange,
  } = useChatErrorHandlers(isPaid);
  const quotaNudge = useQuotaNudge({ isPaid });
  const activeChatId = draft.activeChatId;

  const onFirstReplyRef = useRef<(id?: string | null) => Promise<void>>(async () => {});
  const showActionBannerRef = useRef<
    (message: string, icon?: IconName) => void
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
    sendStart,
    rejectedSend,
    retryRejectedSend,
    restoreRejectedAttachmentDraft,
    beginRegenerateUi,
    cancelRegenerateUi,
    regenerateResponse,
    stopGeneration,
    connect,
  } = useChat(token, activeChatId, {
    onFirstReply: () => onFirstReplyRef.current(),
    onError: handleChatError,
    onTodosSync: handleTodosSync,
    onUsage: quotaNudge.applyTurnUsage,
  });

  const llmBusy = streaming || finalizing;
  const imageGeneratingRef = useRef(false);
  const stopTurnRef = useRef<() => void>(() => {});
  const stopTurn = useCallback(() => {
    stopTurnRef.current();
  }, []);

  const idleComposerBottomPad = Math.max(insets.bottom, CHAT_COMPOSER_MIN_BOTTOM_PAD);
  const { keyboardHeight, keyboardLift, keyboardSteps, composerAnimatedStyle } = useKeyboardInset({
    idleBottomPad: idleComposerBottomPad,
  });

  const scroll = useChatScroll({
    chatId,
    messagesLength: messages.length,
    streamActive: llmBusy,
    windowHeight,
    keyboardSteps,
  });

  const routeLoader = useChatRouteLoader({
    token,
    routeChatId: typeof routeChatId === "string" ? routeChatId : undefined,
    routeHighlightMessage:
      typeof routeHighlightMessage === "string" ? routeHighlightMessage : undefined,
    router,
    draft,
    chatId,
    setChatId,
    setMessages,
    messages,
    streaming: llmBusy,
    imageGeneratingRef,
    stopGeneration: stopTurn,
    listRef: scroll.listRef,
    showActionBanner: (message, icon) => showActionBannerRef.current(message, icon),
    t,
  });

  const {
    chatTitle, setChatTitle, titleGenerating, pinned, setPinned, archived, setArchived, chatLoading,
    hasMoreOlder, loadingOlder, loadOlderMessages, newerPage, jumpToLatest, highlightedMessageId, startNewChat,
  } = routeLoader;
  useScrollHoldForHighlight(scroll.holdForHighlight, highlightedMessageId !== null && !llmBusy);

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
    t,
  });

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
    handleSaveEmailDraft,
    confirmRename,
    shareVisible,
    closeShare,
    loadTranscriptMessages,
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

  const openUpgradeRef = useRef<((source?: UpgradeSource) => void) | null>(null);

  const notifyOfflineBlocked = useCallback(() => {
    showActionBannerRef.current(t("chat.offline_body"), "cloud-off");
  }, [t]);

  const ensureChatId = useEnsureChatId({ chatId, selectedModel, draft, setChatId, setChatTitle, router });
  const imageGen = useChatImageGeneration({
    token,
    ensureChatId,
    setMessages,
    streaming: llmBusy,
    isPaid,
    isOffline,
    onOpenUpgrade: () => openUpgradeRef.current?.(),
    onOfflineBlocked: notifyOfflineBlocked,
    onScrollToLatest: scroll.scrollToLatest,
    newMessageCountRef: scroll.newMessageCountRef,
    t,
  });
  const streamActive = llmBusy || imageGen.generating;

  useEffect(() => {
    if (!streamActive) handleRejectedSendChange(rejectedSend?.reason ?? null);
  }, [streamActive, rejectedSend, handleRejectedSendChange]);

  useChatStreamLifecycle({ streamActive, replySaving: finalizing, dismissChatError, dismissBusyNotice });

  const send = useChatSend({
    token,
    chatId,
    chatLoading: routeLoader.historyPending,
    routeChatId: typeof routeChatId === "string" ? routeChatId : undefined,
    setChatId,
    setChatTitle,
    router,
    draft,
    scroll,
    // A reply that is only saving (after `stream_end`) does not hold the next send.
    streaming: (streaming && !finalizing) || imageGen.generating,
    sendMessage,
    sendStart,
    setMessages,
    messages,
    selectedModel,
    updateUser,
    locationEnabled: user?.location_enabled === true,
    t,
    onStreamBusy: handleStreamBusy,
    onOfflineBlocked: notifyOfflineBlocked,
    isOffline,
    // A send from a window around an old search hit goes to the newest page first.
    beforeSend: newerPage ? jumpToLatest : undefined,
    imageGenerating: imageGen.generating,
    onGenerateImage: (request) => void imageGen.submitPrompt(request),
  });

  const {
    setInput,
    pendingAttachment,
    removePendingAttachment,
    attachPicking,
    sendPhase,
    attachSheetOpen,
    setAttachSheetOpen,
    handleSend,
    restoreComposerDraft,
    handlePickAttachment,
    handleAttachmentSheetSelect,
    handleMathScanCaptured,
    readScan,
    handleMathScanSolve,
    mathScannerOpen,
    setMathScannerOpen,
  } = send;

  const [mathChromeExtra, setMathChromeExtra] = useState(0);
  const [composerInputExtra, setComposerInputExtra] = useState(0);

  const {
    voiceInputAvailable,
    voiceRecording,
    voiceTranscribing,
    voiceMeterLevel,
    toggleVoiceInput: handleToggleVoiceInput,
    cancelVoiceInput,
  } = useComposerDictation({ token, user, routeChatId, setInput, openUpgradeRef, t });

  // Live talk runs without a saved chat when none can be made, as it always has.
  const ensureLiveTalkChatId = useCallback(() => ensureChatId().catch(() => null), [ensureChatId]);
  const liveTalk = useLiveTalk({
    token,
    chatId,
    ensureChatId: ensureLiveTalkChatId,
    setMessages,
    isOffline,
    onUpgrade: () => openUpgradeRef.current?.("live_talk"),
    onScrollToLatest: scroll.scrollToLatest,
    newMessageCountRef: scroll.newMessageCountRef,
    onFirstReply: (id?: string | null) => {
      void onFirstReplyRef.current(id);
    },
    t,
  });

  const closeAttachSheet = useCallback(() => {
    setAttachSheetOpen(false);
  }, [setAttachSheetOpen]);

  const closeMathScanner = useCallback(() => {
    setMathScannerOpen(false);
  }, [setMathScannerOpen]);
  const openMathScanner = useCallback(() => {
    setMathScannerOpen(true);
  }, [setMathScannerOpen]);

  useEffect(() => setActiveChatIdGlobal(chatId), [chatId]);

  useEffect(
    () =>
      registerNewChat((opts) => {
        dismissChatError();
        startNewChat(opts);
      }),
    [startNewChat, dismissChatError],
  );

  const {
    listRef,
    listBottomPadRef,
    showScrollToBottom,
    scrollAwayCount,
    handleScroll,
    handleScrollEnd,
    listScroll,
  } = scroll;
  const scrollToLatest = newerPage ? () => void jumpToLatest().then(scroll.scrollToLatest) : scroll.scrollToLatest;

  const { draftChatId } = draft;

  useChatDraftWarmup({
    chatId,
    streaming: streamActive,
    draftChatId,
    connect,
  });

  const { regenerate: handleRegenerate, regenerating } = useChatRegenerate({
    token,
    messages,
    updateUser,
    regenerateResponse,
    beginRegenerateUi,
    cancelRegenerateUi,
  });
  const retryChatError = useChatErrorRecovery({
    error: chatError,
    blocked: routeLoader.historyPending || streamActive || regenerating,
    dismiss: dismissChatError,
    retryRejectedSend,
    restoreRejectedAttachmentDraft,
    restoreComposerDraft,
    regenerate: handleRegenerate,
    selectedModel,
  });

  const onSelectSuggestion = useCallback(
    (prompt: string) => {
      void handleSend(prompt);
    },
    [handleSend],
  );

  const { headerTitleLabel, renderItem } = useChatMessageList({
    messages,
    streaming,
    finalizing,
    selectedModel,
    highlightedMessageId,
    sendingMessageId,
    setMenuVisible,
    regenerateResponse: handleRegenerate,
    regenerating,
    handleFeedback,
    onSelectSuggestion: user?.follow_up_suggestions_enabled === false ? undefined : onSelectSuggestion,
    imageGenerating: imageGen.generating,
    onRetryImageGen: imageGen.retry,
  });

  const layout = useChatLayoutMetrics({
    insetsTop: insets.top,
    insetsBottom: insets.bottom,
    windowHeight,
    fontScale,
    keyboardHeight,
    composerHeight: COMPOSER_HEIGHT + composerInputExtra,
    attachmentExtra: composerAttachmentExtra(pendingAttachment),
    mathBarExtra: mathChromeExtra,
    messagesLength: messages.length,
    streaming: streamActive,
    lastMessageId: messages[messages.length - 1]?.id,
  });

  const menuOverlayOpen = isComposerMenuOverlayOpen(attachSheetOpen);
  const menuAnchorRef = useRef<View>(null);

  const chatScreenBody = useChatScreenBodyProps({
    styles: s,
    theme: C,
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
      startNewChat,
      setMenuVisible,
      menuOverlayOpen,
      menuAnchorRef,
    },
    list: {
      listRef,
      messages,
      hasMoreOlder,
      loadingOlder,
      newerPage,
      chatLoading,
      renderItem,
      loadOlderMessages,
      handleScroll,
      handleScrollEnd,
      listScroll,
    },
    handleSend,
    showScrollToBottom,
    scrollAwayCount,
    scrollToLatest,
    attachments: {
      attachSheetOpen,
      closeAttachSheet,
      attachPicking,
      pendingAttachment,
      removePendingAttachment,
      handlePickAttachment,
      handleAttachmentSheetSelect,
      mathScannerOpen,
      closeMathScanner,
      handleMathScanCaptured,
      readScan,
      handleMathScanSolve,
      onOpenMathScanner: openMathScanner,
      onMathChromeHeightChange: setMathChromeExtra,
      onInputFrameExtraChange: setComposerInputExtra,
    },
    quotaNudge,
    chatError,
    isPaid,
    retryChatError,
    dismissChatError,
    composerAnimatedStyle,
    keyboardLift,
    streaming: streamActive,
    replySaving: finalizing,
    sendBusy: routeLoader.historyPending || sendPhase !== "idle",
    sendStatus: sendPhase === "locating" ? t("chat.locating") : undefined,
    stopGeneration: stopTurn,
    isOffline,
    voice: {
      voiceAvailable: voiceInputAvailable,
      voiceRecording,
      voiceTranscribing,
      voiceMeterLevel,
      toggleVoiceInput: handleToggleVoiceInput,
      cancelVoiceInput,
      onLiveTalkPress: liveTalk.open,
    },
    liveTalkSession: liveTalk.visible
      ? {
          muted: liveTalk.muted,
          onClose: liveTalk.close,
          onMutePress: liveTalk.toggleMute,
          onYield: liveTalk.yieldToComposer,
        }
      : null,
  });
  // Bound late for the hooks above, which need them before they exist; set once the render commits.
  useLayoutEffect(() => {
    onFirstReplyRef.current = routeLoader.handleFirstReply;
    showActionBannerRef.current = chatActions.showActionBanner;
    imageGeneratingRef.current = imageGen.generating;
    stopTurnRef.current = () => { imageGen.cancel(); stopGeneration(); dismissChatError(); };
    openUpgradeRef.current = chatScreenBody.openUpgradeSheet;
  });
  const chatScreenBodyProps = chatScreenBody.bodyProps;

  if (!token) return <Redirect href="/login" />;

  return (
    <ChatReplyProviders saveEmailDraft={handleSaveEmailDraft} send={onSelectSuggestion} busy={streamActive || regenerating}>
      <View style={{ flex: 1 }}>
        <ChatScreenBody {...chatScreenBodyProps} />
        <LazyLiveTalkOverlay
          visible={liveTalk.visible}
          phase={liveTalk.phase}
          meterLevel={liveTalk.meterLevel}
          recording={liveTalk.recording}
          headerInset={layout.headerInset}
          composerClearance={layout.composerClearance}
          onToggle={() => void liveTalk.toggle()}
        />

        <ChatScreenMenuSheets
          menuVisible={menuVisible}
          menuAnchorRef={menuAnchorRef}
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
          shareVisible={shareVisible}
          onCloseShare={closeShare}
          loadShareMessages={loadTranscriptMessages}
        />
      </View>
    </ChatReplyProviders>
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
