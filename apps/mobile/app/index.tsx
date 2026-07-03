import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Pressable,
  StyleSheet,
  Text,
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
import { ChatScrollFab } from "@/components/chat/ChatScrollFab";
import { ComposerPickerBackdrop } from "@/components/chat/ComposerPickerBackdrop";
import { ChatActionsSheet } from "@/components/ChatActionsSheet";
import { ChatRenameSheet } from "@/components/ChatRenameSheet";
import { ActionBanner } from "@/components/ActionBanner";
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
import { useChatRouteLoader, useQueuedChatLaunch } from "@/hooks/useChatRouteLoader";
import { useChatScroll } from "@/hooks/useChatScroll";
import { useChatSend } from "@/hooks/useChatSend";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { useDraftChat } from "@/hooks/useDraftChat";
import { useModels } from "@/hooks/useModels";
import { useNetwork } from "@/contexts/NetworkContext";
import { useQuotaNudge } from "@/hooks/useQuotaNudge";
import { UpgradeSheet } from "@/components/UpgradeSheet";
import { ChatInlineError } from "@/components/chat/ChatInlineError";
import { resolveChatError, type ResolvedChatError } from "@/lib/chatErrorMessage";
import { useReminderBadgeCount } from "@/hooks/useReminderBadgeCount";
import { useTodosOptional } from "@/contexts/TodosContext";
import { isComposerMenuOverlayOpen } from "@/lib/chatComposerLogic";
import { confirmGeoLocationAccess } from "@/lib/confirmGeoLocation";
import { ensureNearbyLocation } from "@/lib/ensureNearbyLocation";
import { isAmbiguousLocalPlacesQuery, isGeoQuery } from "@/lib/localPlacesQuery";

function ChatScreen() {
  const { token, user, mergeUser } = useAuth();
  const { projects } = useProjects();
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
    void todosCtx?.refresh({ silent: true });
  }, [todosCtx]);

  const {
    messages,
    setMessages,
    streaming,
    finalizing,
    streamingDraft,
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

  const streamingLen =
    streamActive && streamingDraft
      ? streamingDraft.content.length
      : 0;

  // Refetch the quota nudge when a chat turn finishes (stream active -> idle)
  // so the banner appears promptly once the user crosses the threshold.
  // Also refresh home starters silently — GET /home is not invalidated elsewhere.
  const [quotaRefreshKey, setQuotaRefreshKey] = useState(0);
  const prevStreamActiveRef = useRef(false);
  useEffect(() => {
    if (prevStreamActiveRef.current && !streamActive) {
      setQuotaRefreshKey((k) => k + 1);
      void refreshHome({ silent: true });
    }
    prevStreamActiveRef.current = streamActive;
  }, [streamActive, refreshHome]);
  const quotaNudge = useQuotaNudge({ token, isPro, refreshKey: quotaRefreshKey });

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
    keyboardHeight,
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

  const handleRegenerate = useCallback(
    async (model: string) => {
      if (!token) return;
      const lastUser = [...messages].reverse().find((m) => m.role === "user");
      const queryText = lastUser?.content ?? "";
      let clientGeo = null;
      if (
        queryText &&
        isGeoQuery(queryText) &&
        !isAmbiguousLocalPlacesQuery(queryText)
      ) {
        const allowed = await confirmGeoLocationAccess(t);
        if (!allowed) return;
        clientGeo = await ensureNearbyLocation(token, queryText);
        if (!clientGeo) {
          Alert.alert(
            t("chat.location_required_title"),
            t("chat.location_required_body"),
          );
          return;
        }
        mergeUser({ location: clientGeo.label, location_enabled: true });
      }
      await regenerateResponse(model, clientGeo);
    },
    [token, messages, regenerateResponse, t, mergeUser],
  );

  const { headerTitleLabel, renderItem } = useChatMessageList({
    messages,
    streaming,
    finalizing,
    streamingDraft,
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
    composerLift,
    composerBottomPad,
    composerClearance,
    listBottomPad,
    emptyHeight,
  } = layout;
  listBottomPadRef.current = listBottomPad;
  const menuOverlayOpen = isComposerMenuOverlayOpen(attachSheetOpen);

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
          visible={(showModelPicker || attachSheetOpen) && !drawerOpen}
          onClose={closeComposerPickers}
        />

        {quotaNudge.show && !chatError ? (
          <View style={[s.quotaNudge, { bottom: composerClearance + 8 }]}>
            <Pressable
              style={s.quotaNudgeBody}
              onPress={() => {
                quotaNudge.dismiss();
                setUpgradeVisible(true);
              }}
            >
              <Ionicons
                name="flash-outline"
                size={16}
                color={C.primary}
                style={s.quotaNudgeIcon}
              />
              <Text style={s.quotaNudgeText}>
                {t("chat.quota_nudge_body", { pct: quotaNudge.usedPct })}
              </Text>
            </Pressable>
            <Pressable
              style={s.quotaNudgeCta}
              onPress={() => {
                quotaNudge.dismiss();
                setUpgradeVisible(true);
              }}
            >
              <Text style={s.quotaNudgeCtaText}>{t("chat.quota_nudge_cta")}</Text>
            </Pressable>
            <Pressable onPress={quotaNudge.dismiss} hitSlop={8} style={s.quotaNudgeClose}>
              <Ionicons name="close" size={16} color={C.textTertiary} />
            </Pressable>
          </View>
        ) : null}

        <ChatInlineError
          error={chatError}
          bottom={composerClearance + 8}
          upgradeLabel={!isPro ? t("chat.quota_nudge_cta") : undefined}
          onUpgrade={!isPro ? () => setUpgradeVisible(true) : undefined}
          onDismiss={() => setChatError(null)}
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
          showModelPicker={showModelPicker}
          attachSheetOpen={attachSheetOpen}
          modelOptions={modelOptions}
          selectedModel={selectedModel}
          selectedModelLabel={selectedModelLabel}
          onToggleModelPicker={toggleModelPicker}
          onSelectModel={selectModel}
          onClosePickers={closeComposerPickers}
          onPickAttachment={handlePickAttachment}
          onAttachmentSource={(source) => void handleAttachmentSheetSelect(source)}
          onSend={() => void handleSend()}
          onStop={stopGeneration}
          isOffline={isOffline}
          voiceRecording={voiceRecording}
          voiceTranscribing={voiceTranscribing}
          voiceMeterLevel={voiceMeterLevel}
          onVoicePress={
            voiceInputAvailable ? () => void toggleVoiceInput() : undefined
          }
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
  quotaNudge: {
    position: "absolute",
    left: 8,
    right: 8,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: C.surface,
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 8,
    gap: 8,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
    shadowColor: "#000",
    shadowOpacity: 0.08,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  quotaNudgeBody: { flex: 1, flexDirection: "row", alignItems: "center", gap: 8 },
  quotaNudgeIcon: { flexShrink: 0 },
  quotaNudgeText: { flex: 1, fontSize: 13, color: C.text, lineHeight: 18 },
  quotaNudgeCta: {
    backgroundColor: C.primary,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    flexShrink: 0,
  },
  quotaNudgeCtaText: { color: C.onPrimary, fontSize: 13, fontWeight: "700" },
  quotaNudgeClose: { padding: 4, flexShrink: 0 },
});

export default function HomeScreen() {
  return (
    <DrawerShell>
      <ChatScreen />
    </DrawerShell>
  );
}
