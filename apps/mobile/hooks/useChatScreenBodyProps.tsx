import { useMemo, useState, useCallback, type MutableRefObject, type ReactElement, type RefObject } from "react";
import { FlashListRef, ListRenderItemInfo } from "@shopify/flash-list";
import { Ionicons } from "@expo/vector-icons";
import { type NativeScrollEvent, type NativeSyntheticEvent, type ViewStyle } from "react-native";
import { type AnimatedStyle } from "react-native-reanimated";
import { useRouter } from "expo-router";

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
    icon?: keyof typeof Ionicons.glyphMap;
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
    pendingAttachment: PendingAttachment | null;
    setPendingAttachment: (value: PendingAttachment | null) => void;
    handlePickAttachment: () => void;
    handleAttachmentSheetSelect: (source: AttachmentSource) => void | Promise<void>;
    mathScannerOpen: boolean;
    closeMathScanner: () => void;
    handleMathScanCaptured: (pending: PendingAttachment) => void;
  };
  quotaNudge: QuotaNudge;
  chatError: ResolvedChatError | null;
  isPro: boolean;
  dismissChatError: () => void;
  composerAnimatedStyle?: AnimatedStyle<ViewStyle>;
  input: string;
  setInput: (value: string) => void;
  streaming: boolean;
  /** Which message (if any) the composer is editing in place. */
  editing: {
    editingMessageId: string | null;
    setEditingMessageId: (value: string | null) => void;
  };
  stopGeneration: () => void;
  isOffline: boolean;
  voice: {
    voiceRecording: boolean;
    voiceTranscribing: boolean;
    voiceMeterLevel: number;
    toggleVoiceInput: () => void | Promise<void>;
    cancelVoiceInput: () => void | Promise<void>;
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
  listFooter = null,
  hideHomeStarters = false,
}: UseChatScreenBodyPropsParams): { bodyProps: ChatScreenBodyProps; openUpgradeSheet: () => void } {
  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const openUpgradeSheet = useCallback(() => setUpgradeVisible(true), []);

  const { headerInset, composerClearance, listBottomPad, emptyHeight } = layout;
  listBottomPadRef.current = listBottomPad;

  // Keep list-facing callbacks identity-stable. bodyProps still rebuilds on
  // every keystroke (composer `input`), but ChatMessageList is memo'd — fresh
  // inline arrows here used to defeat that memo and re-render the whole list.
  const onLoadOlder = useCallback(() => {
    void loadOlderMessages();
  }, [loadOlderMessages]);
  const onSelectStarter = useCallback(
    (prompt: string) => {
      void handleSend(prompt);
    },
    [handleSend],
  );
  const onSend = useCallback(() => {
    void handleSend();
  }, [handleSend]);
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
  const onVoiceCancel = useCallback(() => {
    void cancelVoiceInput();
  }, [cancelVoiceInput]);
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
      input,
      onChangeInput: setInput,
      streaming,
      attachBusy,
      pendingAttachment,
      onRemoveAttachment,
      editingMessageId,
      onCancelEdit,
      onPickAttachment: handlePickAttachment,
      onAttachmentSource,
      mathScannerOpen,
      onCloseMathScanner: closeMathScanner,
      onMathScanCaptured: handleMathScanCaptured,
      onSend,
      onStop: stopGeneration,
      isOffline,
      voiceRecording,
      voiceTranscribing,
      voiceMeterLevel,
      onVoicePress,
      onVoiceCancel,
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
      input,
      setInput,
      streaming,
      attachBusy,
      pendingAttachment,
      onRemoveAttachment,
      editingMessageId,
      onCancelEdit,
      handlePickAttachment,
      onAttachmentSource,
      mathScannerOpen,
      closeMathScanner,
      handleMathScanCaptured,
      onSend,
      stopGeneration,
      isOffline,
      voiceRecording,
      voiceTranscribing,
      voiceMeterLevel,
      onVoicePress,
      onVoiceCancel,
      upgradeVisible,
      onCloseUpgrade,
      listFooter,
      hideHomeStarters,
    ],
  );

  return { bodyProps, openUpgradeSheet };
}
