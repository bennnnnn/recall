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
  insetsTop: number;
  router: Router;
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
  listRef: RefObject<FlashListRef<Message> | null>;
  messages: Message[];
  hasMoreOlder: boolean;
  loadingOlder: boolean;
  chatLoading: boolean;
  renderItem: (info: ListRenderItemInfo<Message>) => ReactElement | null;
  loadOlderMessages: () => Promise<void>;
  handleScroll: (event: NativeSyntheticEvent<NativeScrollEvent>) => void;
  handleScrollEnd: () => void;
  handleSend: (prompt?: string) => void | Promise<void>;
  headerTitleLabel: string | null;
  titleGenerating: boolean;
  chatTitle: string | null;
  showIndicator: boolean;
  unseenCount: number;
  startNewChat: () => void;
  setMenuVisible: React.Dispatch<React.SetStateAction<boolean>>;
  menuOverlayOpen: boolean;
  showScrollToBottom: boolean;
  scrollAwayCount: number;
  scrollToLatest: () => void;
  attachSheetOpen: boolean;
  closeAttachSheet: () => void;
  quotaNudge: QuotaNudge;
  chatError: ResolvedChatError | null;
  isPro: boolean;
  dismissChatError: () => void;
  composerAnimatedStyle?: AnimatedStyle<ViewStyle>;
  input: string;
  setInput: (value: string) => void;
  streaming: boolean;
  attachBusy: boolean;
  pendingAttachment: PendingAttachment | null;
  setPendingAttachment: (value: PendingAttachment | null) => void;
  editingMessageId: string | null;
  setEditingMessageId: (value: string | null) => void;
  handlePickAttachment: () => void;
  handleAttachmentSheetSelect: (source: AttachmentSource) => void | Promise<void>;
  stopGeneration: () => void;
  isOffline: boolean;
  voiceRecording: boolean;
  voiceTranscribing: boolean;
  voiceMeterLevel: number;
  toggleVoiceInput: () => void | Promise<void>;
  listFooter?: ReactElement | null;
  hideHomeStarters?: boolean;
};

export function useChatScreenBodyProps({
  styles,
  theme,
  token,
  drawerOpen,
  insetsTop,
  router,
  routeChatId,
  layout,
  listBottomPadRef,
  actionBanner,
  dismissActionBanner,
  listRef,
  messages,
  hasMoreOlder,
  loadingOlder,
  chatLoading,
  renderItem,
  loadOlderMessages,
  handleScroll,
  handleScrollEnd,
  handleSend,
  headerTitleLabel,
  titleGenerating,
  chatTitle,
  showIndicator,
  unseenCount,
  startNewChat,
  setMenuVisible,
  menuOverlayOpen,
  showScrollToBottom,
  scrollAwayCount,
  scrollToLatest,
  attachSheetOpen,
  closeAttachSheet,
  quotaNudge,
  chatError,
  isPro,
  dismissChatError,
  composerAnimatedStyle,
  input,
  setInput,
  streaming,
  attachBusy,
  pendingAttachment,
  setPendingAttachment,
  editingMessageId,
  setEditingMessageId,
  handlePickAttachment,
  handleAttachmentSheetSelect,
  stopGeneration,
  isOffline,
  voiceRecording,
  voiceTranscribing,
  voiceMeterLevel,
  toggleVoiceInput,
  listFooter = null,
  hideHomeStarters = false,
}: UseChatScreenBodyPropsParams): { bodyProps: ChatScreenBodyProps; openUpgradeSheet: () => void } {
  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const openUpgradeSheet = useCallback(() => setUpgradeVisible(true), []);

  const { headerInset, composerClearance, listBottomPad, emptyHeight } = layout;
  listBottomPadRef.current = listBottomPad;

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
          hasMessages={messages.length > 0}
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
      onLoadOlder: () => void loadOlderMessages(),
      onScroll: handleScroll,
      onScrollEnd: handleScrollEnd,
      onSelectStarter: (prompt) => void handleSend(prompt),
      listHeader,
      showScrollToBottom,
      scrollAwayCount,
      onScrollToLatest: scrollToLatest,
      attachSheetOpen,
      onCloseAttachSheet: closeAttachSheet,
      quotaNudgeVisible: quotaNudge.show,
      quotaUsedPct: quotaNudge.usedPct,
      onQuotaUpgrade: () => {
        quotaNudge.dismiss();
        setUpgradeVisible(true);
      },
      onQuotaDismiss: quotaNudge.dismiss,
      chatError,
      isPro,
      onUpgrade: () => setUpgradeVisible(true),
      onDismissChatError: dismissChatError,
      composerAnimatedStyle,
      input,
      onChangeInput: setInput,
      streaming,
      attachBusy,
      pendingAttachment,
      onRemoveAttachment: () => setPendingAttachment(null),
      editingMessageId,
      onCancelEdit: () => {
        setEditingMessageId(null);
        setInput("");
      },
      onPickAttachment: handlePickAttachment,
      onAttachmentSource: (source) => void handleAttachmentSheetSelect(source),
      onSend: () => void handleSend(),
      onStop: stopGeneration,
      isOffline,
      voiceRecording,
      voiceTranscribing,
      voiceMeterLevel,
      onVoicePress: () => void toggleVoiceInput(),
      upgradeVisible,
      onCloseUpgrade: () => setUpgradeVisible(false),
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
      loadOlderMessages,
      handleScroll,
      handleScrollEnd,
      handleSend,
      listHeader,
      showScrollToBottom,
      scrollAwayCount,
      scrollToLatest,
      attachSheetOpen,
      closeAttachSheet,
      quotaNudge,
      chatError,
      isPro,
      dismissChatError,
      composerAnimatedStyle,
      input,
      setInput,
      streaming,
      attachBusy,
      pendingAttachment,
      setPendingAttachment,
      editingMessageId,
      setEditingMessageId,
      handlePickAttachment,
      handleAttachmentSheetSelect,
      stopGeneration,
      isOffline,
      voiceRecording,
      voiceTranscribing,
      voiceMeterLevel,
      toggleVoiceInput,
      upgradeVisible,
      listFooter,
      hideHomeStarters,
    ],
  );

  return { bodyProps, openUpgradeSheet };
}
