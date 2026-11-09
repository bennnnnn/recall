import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  useWindowDimensions,
  View,
  type HostInstance,
} from "react-native";
import { registerNewChat, setActiveChatIdGlobal } from "@/features/chat/drawer/drawer";
import { Redirect, useLocalSearchParams, useNavigation, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { AndroidBackScreen } from "@/ui/overlay/useAndroidBack";
import { useTheme } from "@/lib/theme";
import { useLatestRef } from "@/lib/latestRef";
import { ChatScreenBody } from "@/features/chat/components/ChatScreenBody";
import { ChatScreenMenuSheets } from "@/features/chat/components/ChatScreenMenuSheets";
import { chatMenuSheetProps } from "@/features/chat/components/chatMenuSheetProps";
import { LazyLiveTalkOverlay } from "@/features/speech/components/LazyLiveTalkOverlay";
import { makeChatScreenStyles } from "@/features/chat/components/chatScreenStyles";
import { COMPOSER_HEIGHT } from "@/features/chat/components/ChatComposer";
import { composerAttachmentExtra } from "@/features/attachments/components/ComposerAttachmentPreview";
import { DrawerShell } from "@/features/chat/drawer/DrawerShell";
import { ComposerDraftProvider, useComposerDraftActivity } from "@/features/chat/context/ComposerDraftContext";
import { ChatReplyProviders } from "@/features/chat/components/ChatReplyProviders";
import { useAuth } from "@/contexts/AuthContext";
import { useChat } from "@/features/chat/hooks/useChat";
import { useChatActions } from "@/features/chat/hooks/useChatActions";
import { useChatComposerState } from "@/features/chat/hooks/useChatComposerState";
import { useEnsureChatId } from "@/features/chat/hooks/useEnsureChatId";
import { useChatComposerWiring } from "@/features/chat/hooks/useChatComposerWiring";
import { useChatLayoutMetrics } from "@/features/chat/hooks/useChatLayoutMetrics";
import { useChatMessageList } from "@/features/chat/hooks/useChatMessageList";
import { useChatMetadata } from "@/features/chat/hooks/useChatMetadata";
import { useChatRegenerate } from "@/features/chat/hooks/useChatRegenerate";
import { useChatRouteLoader } from "@/features/chat/hooks/useChatRouteLoader";
import { useChatScroll, useScrollHoldForHighlight } from "@/features/chat/hooks/useChatScroll";
import { useChatSend } from "@/features/chat/hooks/useChatSend";
import { useDraftChat } from "@/features/chat/hooks/useDraftChat";
import { useUpgradeSheet } from "@/features/chat/hooks/useUpgradeSheet";
import { useModels } from "@/hooks/useModels";
import { useNetwork } from "@/contexts/NetworkContext";
import { useChatErrorHandlers, useChatErrorRecovery, useChatStreamLifecycle } from "@/features/chat/hooks/useChatErrorHandlers";
import { useQuotaNudge } from "@/features/chat/hooks/useQuotaNudge";
import { useChatScreenBodyProps } from "@/features/chat/hooks/useChatScreenBodyProps";
import { useWelcomePlans } from "@/features/billing/hooks/useWelcomePlans";
import { useTodosOptional } from "@/features/todos/context/TodosContext";
import { isComposerMenuOverlayOpen, CHAT_COMPOSER_MIN_BOTTOM_PAD } from "@/features/chat/model/composerLogic";
import { locationSwitchOf } from "@/features/chat/model/resolveClientGeoForQuery";
import { useChatImageGeneration } from "@/features/chat/hooks/useChatImageGeneration";
import { useKeyboardInset } from "@/hooks/useKeyboardInset";
import type { FirstReply } from "@/features/chat/model/chatTurnCore";

/** The route's chat and the message a search hit opens it at; anything but one id names none. */
function useChatRouteParams() {
  const params = useLocalSearchParams<{ chatId?: string; highlightMessage?: string }>();
  return {
    routeChatId: typeof params.chatId === "string" ? params.chatId : undefined,
    routeHighlightMessage: typeof params.highlightMessage === "string" ? params.highlightMessage : undefined,
  };
}

function ChatScreen() {
  const { token, user, updateUser, profileValidated } = useAuth();
  // The launch cache holds no Location switch: "unknown" until the server has said.
  const locationSwitch = locationSwitchOf(user?.location_enabled, profileValidated);
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeChatScreenStyles(C), [C]);
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { height: windowHeight, fontScale } = useWindowDimensions();
  const { routeChatId, routeHighlightMessage } = useChatRouteParams();

  const [chatId, setChatId] = useState<string | null>(null);
  const composerActive = useComposerDraftActivity();
  const draft = useDraftChat({ chatId, intent: composerActive });
  const { isPaid, autoEnabled, modelEnabledSet, AUTO_MODEL_ID } = useModels();
  const errors = useChatErrorHandlers(isPaid);
  const { chatError, dismissChatError } = errors;
  const quotaNudge = useQuotaNudge({ isPaid });
  // The one hook cycle left: useChat calls it on the first reply, and the title poll that
  // answers it (the route loader's) reads the thread useChat holds. Bound once the render commits.
  const onFirstReplyRef = useRef<(id?: string | null, reply?: FirstReply) => Promise<void>>(async () => {});
  const todosCtx = useTodosOptional();
  const handleTodosSync = useCallback(() => {
    void todosCtx?.refresh({ silent: true, force: true });
  }, [todosCtx]);
  const chat = useChat(token, draft.activeChatId, {
    onFirstReply: (reply) => onFirstReplyRef.current(undefined, reply),
    onError: errors.handleChatError,
    onTodosSync: handleTodosSync,
    onUsage: quotaNudge.applyTurnUsage,
  });
  const { messages, editThread, streaming, finalizing, stopGeneration } = chat;
  const llmBusy = streaming || finalizing;

  const idleComposerBottomPad = Math.max(insets.bottom, CHAT_COMPOSER_MIN_BOTTOM_PAD);
  const keyboard = useKeyboardInset({ idleBottomPad: idleComposerBottomPad });
  const scroll = useChatScroll({
    chatId, messagesLength: messages.length, streamActive: llmBusy, windowHeight, keyboardSteps: keyboard.keyboardSteps,
  });
  const metadata = useChatMetadata(chatId);
  const chatActions = useChatActions({ token, chatId, messages, editThread, t, ...metadata });
  const { showActionBanner } = chatActions;
  const { selectedModel } = useChatComposerState({ autoEnabled, modelEnabledSet, autoModelId: AUTO_MODEL_ID });
  const { isOffline } = useNetwork();
  const upgrade = useUpgradeSheet();
  const notifyOfflineBlocked = useCallback(() => {
    showActionBanner(t("chat.offline_body"), "cloud-off");
  }, [showActionBanner, t]);
  const ensureChatId = useEnsureChatId({
    chatId, selectedModel, draft, setChatId, setChatTitle: metadata.setChatTitle, router,
  });
  const imageGen = useChatImageGeneration({
    token, ensureChatId, editThread, streaming: llmBusy, isPaid, isOffline, onOpenUpgrade: upgrade.open,
    onOfflineBlocked: notifyOfflineBlocked, onScrollToLatest: scroll.scrollToLatest,
    newMessageCountRef: scroll.newMessageCountRef, t,
  });
  const streamActive = llmBusy || imageGen.generating;
  // Stop ends what is under way when it is tapped: a picture, the reply, and its error.
  const stopTurnRef = useLatestRef(() => { imageGen.cancel(); stopGeneration(); dismissChatError(); });
  const stopTurn = useCallback(() => stopTurnRef.current(), [stopTurnRef]);

  const routeLoader = useChatRouteLoader({
    token, routeChatId, routeHighlightMessage, router, draft, chatId, setChatId, editThread, messages,
    streaming: llmBusy, imageGenerating: imageGen.generating, stopGeneration: stopTurn, listRef: scroll.listRef,
    metadata, showActionBanner, t,
  });
  const { historyPending, newerPage, jumpToLatest, highlightedMessageId, startNewChat } = routeLoader;
  useLayoutEffect(() => {
    onFirstReplyRef.current = routeLoader.handleFirstReply;
  });
  useScrollHoldForHighlight(scroll.holdForHighlight, highlightedMessageId !== null && !llmBusy);

  const { rejectedSend } = chat;
  const { handleRejectedSendChange } = errors;
  useEffect(() => {
    if (!streamActive) handleRejectedSendChange(rejectedSend?.reason ?? null);
  }, [streamActive, rejectedSend, handleRejectedSendChange]);
  useChatStreamLifecycle({ streamActive, replySaving: finalizing, dismissChatError, dismissBusyNotice: errors.dismissBusyNotice });

  const send = useChatSend({
    token, chatId, chatLoading: historyPending, routeChatId, setChatId, setChatTitle: metadata.setChatTitle, router,
    draft, scroll,
    // A reply that is only saving (after `stream_end`) does not hold the next send.
    streaming: (streaming && !finalizing) || imageGen.generating,
    sendMessage: chat.sendMessage, sendStart: chat.sendStart, editThread, messages, selectedModel, updateUser,
    locationSwitch, t, onStreamBusy: errors.handleStreamBusy, onOfflineBlocked: notifyOfflineBlocked, isOffline,
    // A send shows the newest message, scrolled up or not; from an old search hit's window, the newest page first.
    beforeSend: newerPage ? () => jumpToLatest().then(scroll.scrollToLatest) : async () => scroll.scrollToLatest(),
    imageGenerating: imageGen.generating,
    onGenerateImage: (request) => void imageGen.submitPrompt(request),
  });
  const { sendPhase, sendTappedLine } = send;
  const composerWiring = useChatComposerWiring({
    token, user, routeChatId, chatId, send, scroll, ensureChatId, editThread, isOffline,
    openUpgrade: upgrade.open, onFirstReplyRef, t,
  });
  const { liveTalk } = composerWiring;

  useEffect(() => setActiveChatIdGlobal(chatId), [chatId]);
  useEffect(
    () =>
      registerNewChat((opts) => {
        dismissChatError();
        startNewChat(opts);
      }),
    [startNewChat, dismissChatError],
  );
  const scrollToLatest = newerPage ? () => void jumpToLatest().then(scroll.scrollToLatest) : scroll.scrollToLatest;

  const { regenerate: handleRegenerate, regenerating } = useChatRegenerate({
    token, messages, updateUser, locationSwitch, regenerateResponse: chat.regenerateResponse,
    beginRegenerateUi: chat.beginRegenerateUi, cancelRegenerateUi: chat.cancelRegenerateUi,
  });
  const retryChatError = useChatErrorRecovery({
    error: chatError,
    blocked: historyPending || streamActive || regenerating,
    dismiss: dismissChatError,
    retryRejectedSend: chat.retryRejectedSend,
    restoreRejectedAttachmentDraft: chat.restoreRejectedAttachmentDraft,
    restoreComposerDraft: send.restoreComposerDraft,
    regenerate: handleRegenerate,
    selectedModel,
  });
  const messageList = useChatMessageList({
    messages, streaming, finalizing, selectedModel, highlightedMessageId, sendingMessageId: chat.sendingMessageId,
    setMenuVisible: chatActions.setMenuVisible, regenerateResponse: handleRegenerate, regenerating,
    handleFeedback: chatActions.handleFeedback,
    onSelectSuggestion: user?.follow_up_suggestions_enabled === false ? undefined : sendTappedLine,
    imageGenerating: imageGen.generating, onRetryImageGen: imageGen.retry,
  });
  const layout = useChatLayoutMetrics({
    insetsTop: insets.top, insetsBottom: insets.bottom, windowHeight, fontScale,
    keyboardHeight: keyboard.keyboardHeight, composerHeight: COMPOSER_HEIGHT + composerWiring.composerInputExtra,
    attachmentExtra: composerAttachmentExtra(send.pendingAttachment), mathBarExtra: composerWiring.mathChromeExtra,
    messagesLength: messages.length, streaming: streamActive, lastMessageId: messages[messages.length - 1]?.id,
  });

  const menuOverlayOpen = isComposerMenuOverlayOpen(send.attachSheetOpen);
  const menuAnchorRef = useRef<HostInstance>(null);
  const bodyProps = useChatScreenBodyProps({
    styles: s, theme: C, routeChatId, insetsTop: insets.top, router, layout, keyboard, scroll, scrollToLatest,
    messages, chatTitle: metadata.chatTitle, routeLoader, messageList, chatActions, menuOverlayOpen, menuAnchorRef,
    handleSend: send.handleSend, wiring: composerWiring, quotaNudge, errors, retryChatError, upgrade, isPaid,
    isOffline, streaming: streamActive, replySaving: finalizing, sendBusy: historyPending || sendPhase !== "idle",
    sendStatus: sendPhase === "locating" ? t("chat.locating") : undefined, stopGeneration: stopTurn,
    liveTalkActive: liveTalk.visible,
  });
  useWelcomePlans({ user, busy: streamActive || regenerating, outOfCredit: quotaNudge.usedPct >= 100 || chatError?.kind === "quota", open: upgrade.open });

  if (!token) return <Redirect href="/login" />;

  const { chatTitle, pinned, archived } = metadata;
  return (
    <ChatReplyProviders saveEmailDraft={chatActions.handleSaveEmailDraft} send={sendTappedLine} busy={streamActive || regenerating}>
      <View style={{ flex: 1 }}>
        <ChatScreenBody {...bodyProps} />
        <LazyLiveTalkOverlay
          visible={liveTalk.visible}
          call={liveTalk}
          headerInset={layout.headerInset}
          bottomInset={idleComposerBottomPad}
        />

        <ChatScreenMenuSheets menuAnchorRef={menuAnchorRef} {...chatMenuSheetProps(chatActions, { chatTitle, pinned, archived })} />
      </View>
    </ChatReplyProviders>
  );
}

export default function HomeScreen() {
  const navigation = useNavigation();
  return (
    <AndroidBackScreen isOnTop={navigation.isFocused}>
      <DrawerShell>
        <ComposerDraftProvider>
          <ChatScreen />
        </ComposerDraftProvider>
      </DrawerShell>
    </AndroidBackScreen>
  );
}
