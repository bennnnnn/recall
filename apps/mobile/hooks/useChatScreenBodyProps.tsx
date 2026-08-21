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
import type { ChatScreenBodyProps } from "@/components/chat/ChatScreenBody";
import type { ChatScreenStyles } from "@/components/chat/chatScreenStyles";
import type { AttachmentSource } from "@/components/AttachmentSourceSheet";
import type { Message } from "@/lib/api";
import type { PendingAttachment } from "@/lib/attachments";
import type { ResolvedChatError } from "@/lib/chatErrorMessage";
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
  token: string;
  drawerOpen: boolean;
  routeChatId?: string;
  layout: {
    headerInset: number;
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
    showIndicator: boolean;
    unseenCount: number;
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
    handleMathScanCaptured: (pending: PendingAttachment) => void;
    onOpenMathScanner?: () => void;
    onMathChromeHeightChange?: (height: number) => void;
  };
  quotaNudge: QuotaNudge;
  chatError: ResolvedChatError | null;
  isPro: boolean;
  dismissChatError: () => void;
  composerAnimatedStyle?: AnimatedStyle<ViewStyle>;
  setInput: (value: string) => void;
  streaming: boolean;
  sendBusy: boolean;
  /** Which message (if any) the composer is editing in place. */
  editing: {
    editingMessageId: string | null;
    setEditingMessageId: (value: string | null) => void;
  };
  stopGeneration: () => void;
  isOffline: boolean;
  voice: {
    voiceAvailable: boolean;
    voiceRecording: boolean;
    voiceTranscribing: boolean;
    voiceMeterLevel: number;
    toggleVoiceInput: () => void | Promise<void>;
  };
  listFooter?: ReactElement | null;
  hideHomeStarters?: boolean;
};

export function useChatScreenBodyProps({
  styles,
  theme,
  token,
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
    showIndicator,
    unseenCount,
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
  dismissChatError,
  composerAnimatedStyle,
  setInput,
  streaming,
  sendBusy,
  editing: { editingMessageId, setEditingMessageId },
  stopGeneration,
  isOffline,
  voice: {
    voiceAvailable,
    voiceRecording,
    voiceTranscribing,
    voiceMeterLevel,
    toggleVoiceInput,
  },
  listFooter = null,
  hideHomeStarters = false,
}: UseChatScreenBodyPropsParams): { bodyProps: ChatScreenBodyProps; openUpgradeSheet: () => void } {
  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const openUpgradeSheet = useCallback(() => setUpgradeVisible(true), []);

  const { headerInset, composerClearance, listBottomPad, emptyHeight } = layout;
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
  const onQuotaUpgrade = useCallback(() => {
    quotaNudge.dismiss();
    setUpgradeVisible(true);
  }, [quotaNudge]);
  const onUpgrade = useCallback(() => setUpgradeVisible(true), []);
  const onRemoveAttachment = useCallback(() => setPendingAttachment(null), [setPendingAttachment]);
  const onCancelEdit = useCallback(() => {
    setEditingMessageId(null);
    setInput("");
  }, [setEditingMessageId, setInput]);
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

  const listHeader = useMemo(
    () =>
      !drawerOpen ? (
        <ChatHeader
          paddingTop={insetsTop}
          height={headerInset}
          menuOverlayOpen={menuOverlayOpen}
          headerTitleLabel={headerTitleLabel}
          titleGenerating={titleGenerating}
          chatTitle={chatTitle}
          showIndicator={showIndicator}
          unseenCount={unseenCount}
          // Prefer routeChatId so actions don't flash off if messages briefly
          // clear during a chat load/refetch; home (no route, no turns) stays clean.
          hasMessages={messages.length > 0 || Boolean(routeChatId)}
          onOpenDrawer={openDrawer}
          onOpenReminders={() =>
            router.push({ pathname: "/todos", params: { focus: "reminders" } })
          }
          onNewChat={startNewChat}
          onOpenMenu={() => setMenuVisible((v) => !v)}
        />
      ) : null,
    [
      drawerOpen,
      insetsTop,
      headerInset,
      menuOverlayOpen,
      headerTitleLabel,
      titleGenerating,
      chatTitle,
      showIndicator,
      unseenCount,
      messages.length,
      routeChatId,
      startNewChat,
      setMenuVisible,
      router,
    ],
  );

  const bodyProps = useMemo(
    (): ChatScreenBodyProps => ({
      styles,
      theme,
      token,
      drawerOpen,
      composerClearance,
      actionBanner,
      onDismissActionBanner: dismissActionBanner,
      listRef,
      messages,
      headerInset,
      listBottomPad,
      hasMoreOlder,
      loadingOlder,
      chatLoading,
      routeChatId,
      emptyHeight,
      renderItem,
      onLoadOlder,
      onScroll: handleScroll,
      onScrollEnd: handleScrollEnd,
      onSelectStarter,
      listHeader,
      showScrollToBottom,
      scrollAwayCount,
      onScrollToLatest: scrollToLatest,
      attachSheetOpen,
      onCloseAttachSheet: closeAttachSheet,
      quotaNudgeVisible: quotaNudge.show,
      quotaUsedPct: quotaNudge.usedPct,
      onQuotaUpgrade,
      onQuotaDismiss: quotaNudge.dismiss,
      chatError,
      isPro,
      onUpgrade,
      onDismissChatError: dismissChatError,
      composerAnimatedStyle,
      streaming,
      attachBusy,
      attachPicking,
      sendBusy,
      pendingAttachment,
      onRemoveAttachment,
      editingMessageId,
      onCancelEdit,
      onPickAttachment: handlePickAttachment,
      onAttachmentSource,
      mathScannerOpen,
      onCloseMathScanner: closeMathScanner,
      onMathScanCaptured: handleMathScanCaptured,
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
      upgradeVisible,
      onCloseUpgrade,
      listFooter,
      hideHomeStarters,
    }),
    [
      styles,
      theme,
      token,
      drawerOpen,
      composerClearance,
      actionBanner,
      dismissActionBanner,
      listRef,
      messages,
      headerInset,
      listBottomPad,
      hasMoreOlder,
      loadingOlder,
      chatLoading,
      routeChatId,
      emptyHeight,
      renderItem,
      onLoadOlder,
      handleScroll,
      handleScrollEnd,
      onSelectStarter,
      listHeader,
      showScrollToBottom,
      scrollAwayCount,
      scrollToLatest,
      attachSheetOpen,
      closeAttachSheet,
      quotaNudge,
      onQuotaUpgrade,
      chatError,
      isPro,
      onUpgrade,
      dismissChatError,
      composerAnimatedStyle,
      setInput,
      streaming,
      attachBusy,
      attachPicking,
      sendBusy,
      pendingAttachment,
      onRemoveAttachment,
      editingMessageId,
      onCancelEdit,
      handlePickAttachment,
      onAttachmentSource,
      mathScannerOpen,
      closeMathScanner,
      handleMathScanCaptured,
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
      upgradeVisible,
      onCloseUpgrade,
      listFooter,
      hideHomeStarters,
    ],
  );

  return { bodyProps, openUpgradeSheet };
}
