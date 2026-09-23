import {
  useEffect,
  useMemo,
  useRef,
  useState,
  useCallback,
  type MutableRefObject,
  type ReactElement,
  type RefObject,
} from "react";
import { FlashListRef, ListRenderItemInfo } from "@shopify/flash-list";
import { type NativeScrollEvent, type NativeSyntheticEvent, type ViewStyle } from "react-native";
import { type AnimatedStyle } from "react-native-reanimated";
import { useRouter } from "expo-router";

import { type IoniconName } from "@/lib/icons";

type Router = ReturnType<typeof useRouter>;

import { ChatHeader } from "@/components/chat/ChatHeader";
import type {
  ChatScreenBodyProps,
  ChatScreenChromeProps,
  ChatScreenComposerProps,
  ChatScreenLayoutProps,
  ChatScreenListProps,
  ChatScreenSheetsProps,
} from "@/components/chat/ChatScreenBody";
import type { ChatScreenStyles } from "@/components/chat/chatScreenStyles";
import type { AttachmentSource } from "@/features/attachments/components/AttachmentSourceSheet";
import type { Message } from "@/lib/api";
import type { PendingAttachment } from "@/features/attachments/model/attachments";
import type { ScannerSubject } from "@/lib/scanner/subjects";
import type { ResolvedChatError } from "@/lib/chat/errorMessage";
import { openDrawer } from "@/lib/drawer";
import type { Theme } from "@/lib/theme";

type QuotaNudge = {
  show: boolean;
  usedPct: number;
  dismiss: () => void;
};

export type UseChatScreenBodyPropsParams = {
  styles: ChatScreenStyles;
  theme: Theme;
  drawerOpen: boolean;
  routeChatId?: string;
  layout: {
    headerMinimumHeight: number;
    headerInset: number;
    onHeaderHeightChange: (height: number) => void;
    composerClearance: number;
    listBottomPad: number;
    emptyHeight: number;
  };
  listBottomPadRef: MutableRefObject<number>;
  actionBanner: {
    message: string;
    icon?: IoniconName;
  } | null;
  dismissActionBanner: () => void;
  /** Everything needed to render the collapsible ChatHeader (title, nav, menu). */
  header: {
    insetsTop: number;
    router: Router;
    headerTitleLabel: string | null;
    titleGenerating: boolean;
    chatTitle: string | null;
    startNewChat: (opts?: { force?: boolean }) => void;
    setMenuVisible: React.Dispatch<React.SetStateAction<boolean>>;
    menuOverlayOpen: boolean;
  };
  /** Message list data + scroll/pagination handlers for ChatMessageList. */
  list: {
    listRef: RefObject<FlashListRef<Message> | null>;
    messages: Message[];
    hasMoreOlder: boolean;
    loadingOlder: boolean;
    chatLoading: boolean;
    renderItem: (info: ListRenderItemInfo<Message>) => ReactElement | null;
    loadOlderMessages: () => Promise<void>;
    handleScroll: (event: NativeSyntheticEvent<NativeScrollEvent>) => void;
    handleScrollEnd: () => void;
  };
  handleSend: (prompt?: string) => void | Promise<void>;
  showScrollToBottom: boolean;
  scrollAwayCount: number;
  scrollToLatest: () => void;
  /** Attachment picker sheet + upload state. */
  attachments: {
    attachSheetOpen: boolean;
    closeAttachSheet: () => void;
    attachBusy: boolean;
    attachPicking: boolean;
    pendingAttachment: PendingAttachment | null;
    setPendingAttachment: (value: PendingAttachment | null) => void;
    handlePickAttachment: () => void;
    handleAttachmentSheetSelect: (source: AttachmentSource) => void | Promise<void>;
    mathScannerOpen: boolean;
    closeMathScanner: () => void;
    handleMathScanCaptured: (pending: PendingAttachment, subject: ScannerSubject) => void;
    onOpenMathScanner?: () => void;
    onMathChromeHeightChange?: (height: number) => void;
  };
  quotaNudge: QuotaNudge;
  chatError: ResolvedChatError | null;
  isPro: boolean;
  retryChatError: () => void;
  dismissChatError: () => void;
  composerAnimatedStyle?: AnimatedStyle<ViewStyle>;
  streaming: boolean;
  sendBusy: boolean;
  sendStatus?: string;
  stopGeneration: () => void;
  isOffline: boolean;
  voice: {
    voiceAvailable: boolean;
    voiceRecording: boolean;
    voiceTranscribing: boolean;
    voiceMeterLevel: number;
    toggleVoiceInput: () => void | Promise<void>;
    onLiveTalkPress?: () => void;
  };
  liveTalkSession?: {
    muted: boolean;
    onClose: () => void;
    onMutePress: () => void;
    onYield: () => void;
  } | null;
  listFooter?: ReactElement | null;
  hideHomeStarters?: boolean;
};

export function useChatScreenBodyProps({
  styles,
  theme,
  drawerOpen,
  routeChatId,
  layout,
  listBottomPadRef,
  actionBanner,
  dismissActionBanner,
  header: {
    insetsTop,
    router,
    headerTitleLabel,
    titleGenerating,
    chatTitle,
    startNewChat,
    setMenuVisible,
    menuOverlayOpen,
  },
  list: {
    listRef,
    messages,
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
    onOpenMathScanner,
    onMathChromeHeightChange,
  },
  quotaNudge,
  chatError,
  isPro,
  retryChatError,
  dismissChatError,
  composerAnimatedStyle,
  streaming,
  sendBusy,
  sendStatus,
  stopGeneration,
  isOffline,
  voice: {
    voiceAvailable,
    voiceRecording,
    voiceTranscribing,
    voiceMeterLevel,
    toggleVoiceInput,
    onLiveTalkPress,
  },
  liveTalkSession = null,
  listFooter = null,
  hideHomeStarters = false,
}: UseChatScreenBodyPropsParams): { bodyProps: ChatScreenBodyProps; openUpgradeSheet: () => void } {
  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const openUpgradeSheet = useCallback(() => setUpgradeVisible(true), []);

  const {
    headerMinimumHeight,
    headerInset,
    onHeaderHeightChange,
    composerClearance,
    listBottomPad,
    emptyHeight,
  } = layout;
  listBottomPadRef.current = listBottomPad;

  // Keep list-facing callbacks identity-stable. Composer text lives in
  // ComposerDraftContext so keystrokes do not rebuild bodyProps.
  const onLoadOlder = useCallback(() => {
    void loadOlderMessages();
  }, [loadOlderMessages]);
  // "Pick up where we left off" starter carries the source chat_id so we open
  // the original conversation (with its message history) instead of creating
  // a new empty chat — otherwise the assistant has no context and tells the
  // user it doesn't remember the topic.
  const pendingStarterRef = useRef<{ chatId: string; prompt: string } | null>(null);
  const onSelectStarter = useCallback(
    (prompt: string, chatId?: string) => {
      if (chatId) {
        pendingStarterRef.current = { chatId, prompt };
        router.setParams({ chatId });
      } else {
        void handleSend(prompt);
      }
    },
    [handleSend, router],
  );
  // Fire the pending prompt once the target chat finishes loading.
  useEffect(() => {
    const pending = pendingStarterRef.current;
    if (!pending || chatLoading) return;
    if (routeChatId === pending.chatId) {
      pendingStarterRef.current = null;
      void handleSend(pending.prompt);
    }
  }, [routeChatId, chatLoading, handleSend]);
  const onSend = useCallback(
    (text?: string) => {
      void handleSend(text);
    },
    [handleSend],
  );
  const quotaDismiss = quotaNudge.dismiss;
  const onQuotaUpgrade = useCallback(() => {
    quotaDismiss();
    setUpgradeVisible(true);
  }, [quotaDismiss]);
  const onUpgrade = useCallback(() => setUpgradeVisible(true), []);
  const onChangeModel = useCallback(() => {
    dismissChatError();
    router.push("/settings/models");
  }, [dismissChatError, router]);
  const onRemoveAttachment = useCallback(() => setPendingAttachment(null), [setPendingAttachment]);
  const onAttachmentSource = useCallback(
    (source: AttachmentSource) => {
      void handleAttachmentSheetSelect(source);
    },
    [handleAttachmentSheetSelect],
  );
  const onVoicePress = useCallback(() => {
    void toggleVoiceInput();
  }, [toggleVoiceInput]);
  const onCloseUpgrade = useCallback(() => setUpgradeVisible(false), []);
  const stableLiveTalkSession = useMemo(
    () =>
      liveTalkSession
        ? {
            muted: liveTalkSession.muted,
            onClose: liveTalkSession.onClose,
            onMutePress: liveTalkSession.onMutePress,
            onYield: liveTalkSession.onYield,
          }
        : null,
    [
      liveTalkSession?.muted,
      liveTalkSession?.onClose,
      liveTalkSession?.onMutePress,
      liveTalkSession?.onYield,
    ],
  );

  const listHeader = useMemo(
    () =>
      !drawerOpen ? (
        <ChatHeader
          paddingTop={insetsTop}
          minimumHeight={headerMinimumHeight}
          onHeightChange={onHeaderHeightChange}
          menuOverlayOpen={menuOverlayOpen}
          headerTitleLabel={headerTitleLabel}
          titleGenerating={titleGenerating}
          chatTitle={chatTitle}
          // Prefer routeChatId so actions don't flash off if messages briefly
          // clear during a chat load/refetch; home (no route, no turns) stays clean.
          hasMessages={messages.length > 0 || Boolean(routeChatId)}
          onOpenDrawer={openDrawer}
          onNewChat={startNewChat}
          onOpenMenu={() => setMenuVisible((v) => !v)}
        />
      ) : null,
    [
      drawerOpen,
      insetsTop,
      headerMinimumHeight,
      onHeaderHeightChange,
      menuOverlayOpen,
      headerTitleLabel,
      titleGenerating,
      chatTitle,
      messages.length,
      routeChatId,
      startNewChat,
      setMenuVisible,
    ],
  );

  const layoutProps = useMemo(
    (): ChatScreenLayoutProps => ({
      styles,
      theme,
      drawerOpen,
      composerClearance,
      headerInset,
      listBottomPad,
      emptyHeight,
    }),
    [
      styles,
      theme,
      drawerOpen,
      composerClearance,
      headerInset,
      listBottomPad,
      emptyHeight,
    ],
  );

  const listProps = useMemo(
    (): ChatScreenListProps => ({
      listRef,
      messages,
      hasMoreOlder,
      loadingOlder,
      chatLoading,
      routeChatId,
      renderItem,
      onLoadOlder,
      onScroll: handleScroll,
      onScrollEnd: handleScrollEnd,
      onSelectStarter,
      header: listHeader,
      footer: listFooter,
      hideHomeStarters,
    }),
    [
      listRef,
      messages,
      hasMoreOlder,
      loadingOlder,
      chatLoading,
      routeChatId,
      renderItem,
      onLoadOlder,
      handleScroll,
      handleScrollEnd,
      onSelectStarter,
      listHeader,
      listFooter,
      hideHomeStarters,
    ],
  );

  const composerProps = useMemo(
    (): ChatScreenComposerProps => ({
      animatedStyle: composerAnimatedStyle,
      streaming,
      attachBusy,
      attachPicking,
      sendBusy,
      sendStatus,
      pendingAttachment,
      onRemoveAttachment,
      onPickAttachment: handlePickAttachment,
      onOpenMathScanner,
      onMathChromeHeightChange,
      onSend,
      onStop: stopGeneration,
      isOffline,
      voiceAvailable,
      voiceRecording,
      voiceTranscribing,
      voiceMeterLevel,
      onVoicePress,
      onLiveTalkPress,
      liveTalkSession: stableLiveTalkSession,
    }),
    [
      composerAnimatedStyle,
      streaming,
      attachBusy,
      attachPicking,
      sendBusy,
      sendStatus,
      pendingAttachment,
      onRemoveAttachment,
      handlePickAttachment,
      onOpenMathScanner,
      onMathChromeHeightChange,
      onSend,
      stopGeneration,
      isOffline,
      voiceAvailable,
      voiceRecording,
      voiceTranscribing,
      voiceMeterLevel,
      onVoicePress,
      onLiveTalkPress,
      stableLiveTalkSession,
    ],
  );

  const chromeProps = useMemo(
    (): ChatScreenChromeProps => ({
      actionBanner,
      onDismissActionBanner: dismissActionBanner,
      showScrollToBottom,
      scrollAwayCount,
      onScrollToLatest: scrollToLatest,
      quotaNudgeVisible: quotaNudge.show,
      quotaUsedPct: quotaNudge.usedPct,
      onQuotaUpgrade,
      onQuotaDismiss: quotaDismiss,
      chatError,
      isPro,
      onUpgrade,
      onRetryChatError: retryChatError,
      onChangeModel,
      onDismissChatError: dismissChatError,
    }),
    [
      actionBanner,
      dismissActionBanner,
      showScrollToBottom,
      scrollAwayCount,
      scrollToLatest,
      quotaNudge.show,
      quotaNudge.usedPct,
      onQuotaUpgrade,
      quotaDismiss,
      chatError,
      isPro,
      onUpgrade,
      retryChatError,
      onChangeModel,
      dismissChatError,
    ],
  );

  const sheetsProps = useMemo(
    (): ChatScreenSheetsProps => ({
      attachSheetOpen,
      onCloseAttachSheet: closeAttachSheet,
      onAttachmentSource,
      mathScannerOpen,
      onCloseMathScanner: closeMathScanner,
      onMathScanCaptured: handleMathScanCaptured,
      upgradeVisible,
      onCloseUpgrade,
    }),
    [
      attachSheetOpen,
      closeAttachSheet,
      onAttachmentSource,
      mathScannerOpen,
      closeMathScanner,
      handleMathScanCaptured,
      upgradeVisible,
      onCloseUpgrade,
    ],
  );

  const bodyProps = useMemo(
    (): ChatScreenBodyProps => ({
      layout: layoutProps,
      list: listProps,
      composer: composerProps,
      chrome: chromeProps,
      sheets: sheetsProps,
    }),
    [layoutProps, listProps, composerProps, chromeProps, sheetsProps],
  );

  return { bodyProps, openUpgradeSheet };
}
