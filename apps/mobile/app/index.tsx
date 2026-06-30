import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  StyleSheet,
  useWindowDimensions,
  View,
} from "react-native";
import { openDrawer, registerNewChat } from "@/lib/drawer";
import { Redirect, useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Ionicons } from "@expo/vector-icons";

import { Theme, useTheme } from "@/lib/theme";
import { ChatHeader } from "@/components/chat/ChatHeader";
import {
  ChatComposer,
  COMPOSER_HEIGHT,
  composerAttachmentExtra,
} from "@/components/chat/ChatComposer";
import { ChatMessageList } from "@/components/chat/ChatMessageList";
import { ChatMessageRow } from "@/components/chat/ChatMessageRow";
import { ChatScrollFab } from "@/components/chat/ChatScrollFab";
import { ComposerPickerBackdrop } from "@/components/chat/ComposerPickerBackdrop";
import { TemplatesSheet } from "@/components/TemplatesSheet";
import { ChatActionsSheet } from "@/components/ChatActionsSheet";
import { ChatRenameSheet } from "@/components/ChatRenameSheet";
import { ActionBanner } from "@/components/ActionBanner";
import { DrawerShell } from "@/components/DrawerShell";
import { useAuth } from "@/contexts/AuthContext";
import { useDrawer } from "@/contexts/DrawerContext";
import { useChat } from "@/hooks/useChat";
import { useChatActions } from "@/hooks/useChatActions";
import { useChatComposerState } from "@/hooks/useChatComposerState";
import { useChatLayoutMetrics } from "@/hooks/useChatLayoutMetrics";
import { useChatRouteLoader, useQueuedChatLaunch } from "@/hooks/useChatRouteLoader";
import { useChatScroll } from "@/hooks/useChatScroll";
import { useChatSend } from "@/hooks/useChatSend";
import { useDraftChat } from "@/hooks/useDraftChat";
import { useModels } from "@/hooks/useModels";
import { UpgradeSheet } from "@/components/UpgradeSheet";
import { Message } from "@/lib/api";
import { displayChatTitle } from "@/lib/chatTitle";
import { inferQuizAnswersFromMessages } from "@/lib/parseVocabQuiz";
import { isQuotaErrorMessage, quotaAlertTitle } from "@/lib/quota";
import { useReminderBadgeCount } from "@/hooks/useReminderBadgeCount";
import { useTodosOptional } from "@/contexts/TodosContext";
import { shouldPreCreateDraft, shouldWarmDraftSocket } from "@/lib/chatDraftLogic";
import { isComposerMenuOverlayOpen } from "@/lib/chatComposerLogic";

function ChatScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeS(C), [C]);
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { height: windowHeight } = useWindowDimensions();
  const drawerOpen = useDrawer().isOpen;
  const { chatId: routeChatId, prompt: routePrompt, launchId: routeLaunchId, highlightMessage: routeHighlightMessage } =
    useLocalSearchParams<{ chatId?: string; prompt?: string; launchId?: string; highlightMessage?: string }>();

  const [chatId, setChatId] = useState<string | null>(null);
  const [quizLanguage, setQuizLanguage] = useState("en");
  const { isPro, labelFor, autoEnabled, modelEnabledSet, AUTO_MODEL_ID } = useModels();
  const { unseenCount, showIndicator } = useReminderBadgeCount({ enabled: Boolean(token) });
  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const [templatesVisible, setTemplatesVisible] = useState(false);

  const draft = useDraftChat({ token, chatId });
  const activeChatId = draft.activeChatId;

  const onFirstReplyRef = useRef<() => Promise<void>>(async () => {});
  const setInputRef = useRef<(value: string) => void>(() => {});
  const closeAttachSheetRef = useRef<() => void>(() => {});
  const showActionBannerRef = useRef<
    (message: string, icon?: keyof typeof Ionicons.glyphMap) => void
  >(() => {});

  const handleChatError = useCallback(
    (message: string, code?: string) => {
      const isQuota =
        code === "quota_exceeded" || isQuotaErrorMessage(message);
      Alert.alert(
        isQuota ? quotaAlertTitle(isPro, t) : t("chat.error_title"),
        message,
      );
    },
    [isPro, t],
  );

  const todosCtx = useTodosOptional();
  const handleTodosSync = useCallback(() => {
    void todosCtx?.refresh({ silent: true });
  }, [todosCtx]);

  const {
    messages,
    setMessages,
    streaming,
    streamingDraft,
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

  const streamingLen =
    streaming &&
    messages.length > 0 &&
    messages[messages.length - 1]?.id === "streaming"
      ? messages[messages.length - 1].content.length
      : 0;

  const scroll = useChatScroll({
    chatId,
    messagesLength: messages.length,
    streamingLen,
    windowHeight,
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
    streaming,
    stopGeneration,
    setQuizLanguage,
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
    isPro,
    autoEnabled,
    modelEnabledSet,
    labelFor,
    autoModelId: AUTO_MODEL_ID,
    t,
    closeAttachSheetRef,
    onRequestUpgrade: () => setUpgradeVisible(true),
  });

  const { selectedModel, ...composerUi } = composer;

  const send = useChatSend({
    token,
    chatId,
    setChatId,
    setChatTitle,
    router,
    draft,
    scroll,
    streaming,
    sendMessage,
    editMessage,
    setMessages,
    selectedModel,
    pendingLaunch,
    setPendingLaunch,
    pendingLaunchRef,
    t,
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
  } = send;

  closeAttachSheetRef.current = () => setAttachSheetOpen(false);

  const {
    showPlanPicker,
    showModelPicker,
    planLabel,
    modelOptions,
    selectedModelLabel,
    closePickers: closeComposerPickers,
    togglePlanPicker,
    toggleModelPicker,
    selectPlan,
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
    keyboardHeight,
    scrollToLatest,
    handleScroll,
    handleScrollEnd,
  } = scroll;

  const quizAnswers = useMemo(
    () => inferQuizAnswersFromMessages(messages),
    [messages],
  );

  const { prepareDraftChat, draftChatId } = draft;

  // Pre-create an empty chat + warm the WebSocket while the home screen is visible.
  useEffect(() => {
    if (
      !shouldPreCreateDraft({
        token,
        routeChatId: typeof routeChatId === "string" ? routeChatId : undefined,
        chatId,
        messagesLength: messages.length,
        streaming,
      })
    ) {
      return;
    }
    void prepareDraftChat();
  }, [token, routeChatId, chatId, messages.length, streaming, prepareDraftChat]);

  useEffect(() => {
    if (!shouldWarmDraftSocket({ token, draftChatId, chatId, streaming })) return;
    void connect();
  }, [token, draftChatId, chatId, streaming, connect]);

  useEffect(() => {
    if (messages.length === 0) setMenuVisible(false);
  }, [messages.length, setMenuVisible]);

  const lastAssistantId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return messages[i].id;
    }
    return null;
  }, [messages]);

  const headerTitleLabel = useMemo(
    () =>
      messages.length > 0
        ? displayChatTitle(chatTitle, { generating: titleGenerating }, t)
        : null,
    [messages.length, chatTitle, titleGenerating, t],
  );

  const renderItem = useCallback(
    ({ item, index }: { item: Message; index: number }) => (
      <ChatMessageRow
        item={item}
        index={index}
        messages={messages}
        streaming={streaming}
        streamingDraft={streamingDraft}
        lastAssistantId={lastAssistantId}
        selectedModel={selectedModel}
        quizLanguage={quizLanguage}
        quizAnswers={quizAnswers}
        highlightedMessageId={highlightedMessageId}
        quizDisabled={streaming || creatingRef.current}
        onRegenerate={regenerateResponse}
        onEdit={handleEditMessage}
        onFeedback={handleFeedback}
        onQuizAnswer={handleQuizAnswer}
      />
    ),
    [
      messages,
      streaming,
      streamingDraft,
      lastAssistantId,
      selectedModel,
      quizLanguage,
      quizAnswers,
      highlightedMessageId,
      regenerateResponse,
      handleEditMessage,
      handleFeedback,
      handleQuizAnswer,
      creatingRef,
    ],
  );

  const layout = useChatLayoutMetrics({
    insetsTop: insets.top,
    insetsBottom: insets.bottom,
    windowHeight,
    keyboardHeight,
    composerHeight: COMPOSER_HEIGHT,
    attachmentExtra: composerAttachmentExtra(pendingAttachment),
    messagesLength: messages.length,
    streaming,
  });

  if (!token) return <Redirect href="/login" />;

  const {
    headerInset,
    fadeHeight,
    composerLift,
    composerBottomPad,
    composerClearance,
    listBottomPad,
    emptyHeight,
  } = layout;
  listBottomPadRef.current = listBottomPad;
  const menuOverlayOpen = isComposerMenuOverlayOpen(attachSheetOpen, showPlanPicker);

  return (
    <>
      <ChatActionsSheet
        visible={menuVisible}
        title={chatTitle}
        pinned={pinned}
        onClose={() => setMenuVisible(false)}
        onShare={onShareFromMenu}
        onRename={onRenameFromMenu}
        onTogglePin={onTogglePinFromMenu}
        onDelete={onDeleteFromMenu}
      />

      <ChatRenameSheet
        visible={renameVisible}
        value={renameText}
        onChangeText={setRenameText}
        onClose={() => setRenameVisible(false)}
        onSave={() => void confirmRename()}
      />

      <View style={s.container}>
        <ActionBanner
          message={actionBanner?.message ?? null}
          icon={actionBanner?.icon}
          bottomOffset={composerClearance + 12}
          onDismiss={dismissActionBanner}
        />
        <ChatMessageList
          listRef={listRef}
          messages={messages}
          headerInset={headerInset}
          listBottomPad={listBottomPad}
          fadeHeight={fadeHeight}
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
          onOpenTemplates={() => setTemplatesVisible(true)}
          header={
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
            ) : null
          }
        />

        <ChatScrollFab
          visible={!drawerOpen && showScrollToBottom}
          bottomOffset={composerClearance + 8}
          scrollAwayCount={scrollAwayCount}
          onPress={scrollToLatest}
        />

        <ComposerPickerBackdrop
          visible={(showPlanPicker || showModelPicker || attachSheetOpen) && !drawerOpen}
          onClose={closeComposerPickers}
        />

        <ChatComposer
          visible={!drawerOpen}
          bottom={composerLift}
          paddingBottom={composerBottomPad}
          token={token}
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
          showPlanPicker={showPlanPicker}
          showModelPicker={showModelPicker}
          attachSheetOpen={attachSheetOpen}
          isPro={isPro}
          planLabel={planLabel}
          modelOptions={modelOptions}
          selectedModel={selectedModel}
          selectedModelLabel={selectedModelLabel}
          onTogglePlanPicker={togglePlanPicker}
          onToggleModelPicker={toggleModelPicker}
          onSelectPlan={selectPlan}
          onSelectModel={selectModel}
          onClosePickers={closeComposerPickers}
          onPickAttachment={handlePickAttachment}
          onAttachmentSource={(source) => void handleAttachmentSheetSelect(source)}
          onSend={() => void handleSend()}
          onStop={stopGeneration}
        />

        <TemplatesSheet
          visible={templatesVisible}
          token={token}
          onClose={() => setTemplatesVisible(false)}
          onSelect={(content) => void handleSend(content)}
        />
        <UpgradeSheet visible={upgradeVisible} onClose={() => setUpgradeVisible(false)} />
      </View>
    </>
  );
}

const makeS = (C: Theme) => StyleSheet.create({
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: C.bg,
  },
  loadingDot: { fontSize: 48, color: C.primary, opacity: 0.4 },
  container: { flex: 1, backgroundColor: C.bg },
});

export default function HomeScreen() {
  return (
    <DrawerShell>
      <ChatScreen />
    </DrawerShell>
  );
}
