import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  useWindowDimensions,
} from "react-native";
import { openDrawer, registerNewChat } from "@/lib/drawer";
import { Redirect, useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Ionicons } from "@expo/vector-icons";

import { useTheme } from "@/lib/theme";
import { ChatHeader } from "@/components/chat/ChatHeader";
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
import { quizVariantForProjectKind, type QuizVariant } from "@/lib/quizVariant";
import { findLanguageProject } from "@/lib/languageProject";
import { findTriviaProject } from "@/lib/triviaProject";
import { useDrawer } from "@/contexts/DrawerContext";
import { useHome } from "@/contexts/HomeContext";
import { useChat } from "@/hooks/useChat";
import { useChatActions } from "@/hooks/useChatActions";
import { useChatComposerState } from "@/hooks/useChatComposerState";
import { useChatDraftWarmup } from "@/hooks/useChatDraftWarmup";
import { useChatLayoutMetrics } from "@/hooks/useChatLayoutMetrics";
import { useChatMessageList } from "@/hooks/useChatMessageList";
import { useChatRegenerate } from "@/hooks/useChatRegenerate";
import { useChatRouteLoader, useQueuedChatLaunch } from "@/hooks/useChatRouteLoader";
import { useChatScroll } from "@/hooks/useChatScroll";
import { useChatSend } from "@/hooks/useChatSend";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { useDraftChat } from "@/hooks/useDraftChat";
import { useModels } from "@/hooks/useModels";
import { useNetwork } from "@/contexts/NetworkContext";
import { useQuotaNudge } from "@/hooks/useQuotaNudge";
import { resolveChatError, type ResolvedChatError } from "@/lib/chatErrorMessage";
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
  const [quizLanguage, setQuizLanguage] = useState("en");
  const [quizVariant, setQuizVariant] = useState<QuizVariant>("vocab");
  const resolveQuizVariant = useCallback(
    (projectId: string | null | undefined): QuizVariant => {
      if (!projectId) return "vocab";
      const project = projects.find((item) => item.id === projectId);
      return quizVariantForProjectKind(project?.kind);
    },
    [projects],
  );
  const { isPro, labelFor, autoEnabled, modelEnabledSet, AUTO_MODEL_ID, models } = useModels();
  const { unseenCount, showIndicator } = useReminderBadgeCount({ enabled: Boolean(token) });
  const { refresh: refreshHome } = useHome();
  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const [chatError, setChatError] = useState<ResolvedChatError | null>(null);
  const draft = useDraftChat({ token, chatId });
  const activeChatId = draft.activeChatId;
  const resolveQuizProjectId = useCallback((): string | null => {
    const fromDraft = draft.draftProjectIdRef.current;
    if (fromDraft) return fromDraft;
    if (quizVariant === "trivia") {
      return findTriviaProject(projects)?.id ?? null;
    }
    if (quizVariant === "vocab") {
      return findLanguageProject(projects, "en")?.id ?? null;
    }
    return null;
  }, [projects, quizVariant, draft.draftProjectIdRef]);

  const onFirstReplyRef = useRef<() => Promise<void>>(async () => {});
  const setInputRef = useRef<(value: string) => void>(() => {});
  const closeAttachSheetRef = useRef<() => void>(() => {});
  const showActionBannerRef = useRef<
    (message: string, icon?: keyof typeof Ionicons.glyphMap) => void
  >(() => {});

  const handleChatError = useCallback(
    (message: string, code?: string) => {
      setChatError(resolveChatError({ message, code, isPro, t }));
    },
    [isPro, t],
  );

  const handleStreamBusy = useCallback(() => {
    setChatError(resolveChatError({ message: "", code: "busy", isPro, t }));
  }, [isPro, t]);

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

  useEffect(() => {
    if (streamActive) setChatError(null);
  }, [streamActive]);

  // Refetch quota + home when a chat turn finishes (vocab/todos/memory may have changed).
  const [quotaRefreshKey, setQuotaRefreshKey] = useState(0);
  const prevStreamActiveRef = useRef(false);
  useEffect(() => {
    if (prevStreamActiveRef.current && !streamActive) {
      setQuotaRefreshKey((k) => k + 1);
      void refreshHome({ silent: true, force: true });
    }
    prevStreamActiveRef.current = streamActive;
  }, [streamActive, refreshHome]);
  const quotaNudge = useQuotaNudge({ token, isPro, refreshKey: quotaRefreshKey });

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
  } = routeLoader;

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

  const { headerTitleLabel, renderItem } = useChatMessageList({
    messages,
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
    handleQuizAnswer,
  });

  const layout = useChatLayoutMetrics({
    insetsTop: insets.top,
    insetsBottom: insets.bottom,
    windowHeight,
    keyboardHeight,
    composerHeight: COMPOSER_HEIGHT,
    attachmentExtra: composerAttachmentExtra(pendingAttachment),
    messagesLength: messages.length,
    streaming: streamActive,
  });

  if (!token) return <Redirect href="/login" />;

  const {
    headerInset,
    composerClearance,
    listBottomPad,
    emptyHeight,
  } = layout;
  listBottomPadRef.current = listBottomPad;
  const menuOverlayOpen = isComposerMenuOverlayOpen(attachSheetOpen);

  const listHeader =
    !drawerOpen ? (
      <ChatHeader
        paddingTop={insets.top}
        height={headerInset}
        menuOverlayOpen={menuOverlayOpen}
        headerTitleLabel={headerTitleLabel}
        titleGenerating={titleGenerating}
        chatTitle={chatTitle}
        showIndicator={showIndicator}
        unseenCount={unseenCount}
        hasMessages={messages.length > 0}
        onOpenDrawer={openDrawer}
        onOpenReminders={() =>
          router.push({ pathname: "/todos", params: { focus: "reminders" } })
        }
        onNewChat={startNewChat}
        onOpenMenu={() => setMenuVisible((v) => !v)}
      />
    ) : null;

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

      <ChatScreenBody
        styles={s}
        theme={C}
        token={token}
        drawerOpen={drawerOpen}
        composerClearance={composerClearance}
        actionBanner={actionBanner}
        onDismissActionBanner={dismissActionBanner}
        listRef={listRef}
        messages={messages}
        headerInset={headerInset}
        listBottomPad={listBottomPad}
        hasMoreOlder={hasMoreOlder}
        loadingOlder={loadingOlder}
        chatLoading={chatLoading}
        routeChatId={typeof routeChatId === "string" ? routeChatId : undefined}
        emptyHeight={emptyHeight}
        renderItem={renderItem}
        onLoadOlder={() => void loadOlderMessages()}
        onScroll={handleScroll}
        onScrollEnd={handleScrollEnd}
        onSelectStarter={handleSend}
        listHeader={listHeader}
        showScrollToBottom={showScrollToBottom}
        scrollAwayCount={scrollAwayCount}
        onScrollToLatest={scrollToLatest}
        showModelPicker={showModelPicker}
        attachSheetOpen={attachSheetOpen}
        onCloseComposerPickers={closeComposerPickers}
        quotaNudgeVisible={quotaNudge.show}
        quotaUsedPct={quotaNudge.usedPct}
        onQuotaUpgrade={() => {
          quotaNudge.dismiss();
          setUpgradeVisible(true);
        }}
        onQuotaDismiss={quotaNudge.dismiss}
        chatError={chatError}
        isPro={isPro}
        onUpgrade={() => setUpgradeVisible(true)}
        onDismissChatError={() => setChatError(null)}
        composerAnimatedStyle={composerAnimatedStyle}
        input={input}
        onChangeInput={setInput}
        streaming={streaming}
        attachBusy={attachBusy}
        pendingAttachment={pendingAttachment}
        onRemoveAttachment={() => setPendingAttachment(null)}
        editingMessageId={editingMessageId}
        onCancelEdit={() => {
          setEditingMessageId(null);
          setInput("");
        }}
        modelOptions={modelOptions}
        selectedModel={selectedModel}
        selectedModelLabel={selectedModelLabel}
        onToggleModelPicker={toggleModelPicker}
        onSelectModel={selectModel}
        onPickAttachment={handlePickAttachment}
        onAttachmentSource={(source) => void handleAttachmentSheetSelect(source)}
        onSend={() => void handleSend()}
        onStop={stopGeneration}
        isOffline={isOffline}
        voiceRecording={voiceRecording}
        voiceTranscribing={voiceTranscribing}
        voiceMeterLevel={voiceMeterLevel}
        onVoicePress={() => void toggleVoiceInput()}
        upgradeVisible={upgradeVisible}
        onCloseUpgrade={() => setUpgradeVisible(false)}
      />
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
