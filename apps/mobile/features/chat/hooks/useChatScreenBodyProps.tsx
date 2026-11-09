import { useCallback, useLayoutEffect, useMemo, type MutableRefObject, type ReactElement, type RefObject } from "react";
import type { HostInstance } from "react-native";
import type { SharedValue } from "react-native-reanimated";
import type { useRouter } from "expo-router";

import { WhileDrawerClosed } from "@/contexts/DrawerContext";
import { ChatHeader } from "@/features/chat/components/ChatHeader";
import type {
  ChatScreenBodyProps,
  ChatScreenChromeProps,
  ChatScreenComposerProps,
  ChatScreenLayoutProps,
  ChatScreenListProps,
} from "@/features/chat/components/ChatScreenBody";
import type { ChatScreenStyles } from "@/features/chat/components/chatScreenStyles";
import type { useChatActions } from "@/features/chat/hooks/useChatActions";
import type { useChatComposerWiring } from "@/features/chat/hooks/useChatComposerWiring";
import type { useChatErrorHandlers } from "@/features/chat/hooks/useChatErrorHandlers";
import type { useChatLayoutMetrics } from "@/features/chat/hooks/useChatLayoutMetrics";
import type { useChatMessageList } from "@/features/chat/hooks/useChatMessageList";
import type { useChatRouteLoader } from "@/features/chat/hooks/useChatRouteLoader";
import type { ChatListScroll, useChatScroll } from "@/features/chat/hooks/useChatScroll";
import type { useQuotaNudge } from "@/features/chat/hooks/useQuotaNudge";
import type { useUpgradeSheet } from "@/features/chat/hooks/useUpgradeSheet";
import { useSheetsProps } from "@/features/chat/hooks/useSheetsProps";
import type { Message } from "@/lib/api";
import { openDrawer } from "@/features/chat/drawer/drawer";
import type { Theme } from "@/lib/theme";
import type { ComposerKeyboard } from "@/hooks/useKeyboardInset";

type Scroll = ReturnType<typeof useChatScroll>;
type Wiring = ReturnType<typeof useChatComposerWiring>;

/**
 * What the chat screen's hooks hand the body, each as its hook returns it; the body's five
 * groups are made here, each kept as one value while what it shows stays the same.
 */
type Params = {
  styles: ChatScreenStyles;
  theme: Theme;
  /** The chat the route names: the header keeps its actions while a load briefly clears the thread. */
  routeChatId?: string;
  insetsTop: number;
  router: Pick<ReturnType<typeof useRouter>, "push">;
  layout: Pick<ReturnType<typeof useChatLayoutMetrics>, "headerMinimumHeight" | "headerInset" |
    "onHeaderHeightChange" | "emptyHeight" | "listBottomPad" | "restingComposerClearance" | "restingListBottomPad">;
  keyboard: { keyboardLift: SharedValue<number>; composerKeyboard?: ComposerKeyboard };
  scroll: Pick<Scroll, "listRef" | "showScrollToBottom" | "scrollAwayCount" | "handleScroll" | "handleScrollEnd"> & {
    listBottomPadRef: MutableRefObject<number>;
    listScroll?: ChatListScroll;
  };
  /** Jump to latest: from a search hit's window, the newest page first. */
  scrollToLatest: () => void;
  messages: Message[];
  chatTitle: string | null;
  routeLoader: Pick<ReturnType<typeof useChatRouteLoader>, "titleGenerating" | "startNewChat" | "hasMoreOlder" |
    "loadingOlder" | "newerPage" | "chatLoading" | "loadOlderMessages">;
  messageList: Pick<ReturnType<typeof useChatMessageList>, "renderItem"> & { headerTitleLabel: string | null };
  chatActions: Pick<ReturnType<typeof useChatActions>, "setMenuVisible" | "actionBanner" | "dismissActionBanner">;
  menuOverlayOpen: boolean;
  /** The header ⋮ button; the chat menu drops from it. */
  menuAnchorRef: RefObject<HostInstance | null>;
  handleSend: (prompt?: string) => unknown;
  wiring: { attachments: Wiring["attachments"]; voice: Wiring["voice"] };
  quotaNudge: Pick<ReturnType<typeof useQuotaNudge>, "show" | "label" | "dismiss">;
  errors: Pick<ReturnType<typeof useChatErrorHandlers>, "chatError" | "dismissChatError">;
  retryChatError: () => void;
  upgrade: ReturnType<typeof useUpgradeSheet>;
  isPaid: boolean;
  isOffline: boolean;
  streaming: boolean;
  replySaving: boolean;
  sendBusy: boolean;
  sendStatus?: string;
  stopGeneration: () => void;
  liveTalkActive?: boolean;
};

/** The collapsible header; hidden while the drawer is open, which it reads itself, so this screen never re-renders for it. */
function useHeader(p: Params): ReactElement {
  const { insetsTop, routeChatId, menuOverlayOpen, menuAnchorRef, chatTitle } = p;
  const { headerMinimumHeight, onHeaderHeightChange } = p.layout;
  const { headerTitleLabel } = p.messageList;
  const { titleGenerating, startNewChat } = p.routeLoader;
  const { setMenuVisible } = p.chatActions;
  const messagesLength = p.messages.length;
  return useMemo(
    () => (
      <WhileDrawerClosed>
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
          hasMessages={messagesLength > 0 || Boolean(routeChatId)}
          onOpenDrawer={openDrawer}
          onNewChat={startNewChat}
          onOpenMenu={() => setMenuVisible((v) => !v)}
          menuAnchorRef={menuAnchorRef}
        />
      </WhileDrawerClosed>
    ),
    [insetsTop, headerMinimumHeight, onHeaderHeightChange, menuOverlayOpen, headerTitleLabel, titleGenerating,
      chatTitle, messagesLength, routeChatId, startNewChat, setMenuVisible, menuAnchorRef],
  );
}

/** The thread: its rows, paging and scroll handlers, kept identity-stable for FlashList. */
function useListProps(p: Params, header: ReactElement): ChatScreenListProps {
  const { messages, routeChatId } = p;
  const { listRef, handleScroll, handleScrollEnd, listScroll } = p.scroll;
  const { hasMoreOlder, loadingOlder, newerPage, chatLoading, loadOlderMessages } = p.routeLoader;
  const { renderItem } = p.messageList;
  return useMemo(
    () => ({
      listRef, messages, hasMoreOlder, loadingOlder, newerPage, chatLoading, routeChatId, renderItem,
      onLoadOlder: loadOlderMessages, onScroll: handleScroll, onScrollEnd: handleScrollEnd, scroll: listScroll, header,
    }),
    [listRef, messages, hasMoreOlder, loadingOlder, newerPage, chatLoading, routeChatId, renderItem, loadOlderMessages,
      handleScroll, handleScrollEnd, listScroll, header],
  );
}

/** The composer's props. Its text lives in ComposerDraftContext, so keystrokes rebuild none of them. */
function useComposerProps(p: Params): ChatScreenComposerProps {
  const { streaming, replySaving, sendBusy, sendStatus, handleSend, stopGeneration, isOffline, liveTalkActive = false } = p;
  const keyboard = p.keyboard.composerKeyboard;
  const {
    attachPicking, pendingAttachment, removePendingAttachment, handlePickAttachment, onOpenMathScanner,
    onMathChromeHeightChange, onInputFrameExtraChange,
  } = p.wiring.attachments;
  const {
    voiceAvailable, voiceRecording, voiceTranscribing, voiceMeterLevel, toggleVoiceInput, cancelVoiceInput, onLiveTalkPress,
  } = p.wiring.voice;
  return useMemo(
    () => ({
      keyboard, streaming, replySaving, attachPicking, sendBusy, sendStatus, pendingAttachment,
      onRemoveAttachment: removePendingAttachment, onPickAttachment: handlePickAttachment, onOpenMathScanner,
      onMathChromeHeightChange, onInputFrameExtraChange, onSend: handleSend, onStop: stopGeneration, isOffline,
      voiceAvailable, voiceRecording, voiceTranscribing, voiceMeterLevel, onVoicePress: toggleVoiceInput,
      onCancelVoice: cancelVoiceInput, onLiveTalkPress, liveTalkActive,
    }),
    [keyboard, streaming, replySaving, attachPicking, sendBusy, sendStatus, pendingAttachment, removePendingAttachment,
      handlePickAttachment, onOpenMathScanner, onMathChromeHeightChange, onInputFrameExtraChange, handleSend,
      stopGeneration, isOffline, voiceAvailable, voiceRecording, voiceTranscribing, voiceMeterLevel, toggleVoiceInput,
      cancelVoiceInput, onLiveTalkPress, liveTalkActive],
  );
}

/** What floats over the thread: the toast, jump to latest, the quota nudge and an error. */
function useChromeProps(p: Params): ChatScreenChromeProps {
  const { scrollToLatest, isPaid, retryChatError, router } = p;
  const { actionBanner, dismissActionBanner } = p.chatActions;
  const { showScrollToBottom, scrollAwayCount } = p.scroll;
  const { show: quotaNudgeVisible, label: quotaLabel, dismiss: quotaDismiss } = p.quotaNudge;
  const { chatError, dismissChatError } = p.errors;
  const { open: openUpgrade } = p.upgrade;
  // Each is a button's onPress: the press event never reaches the sheet as its source.
  const onQuotaUpgrade = useCallback(() => {
    quotaDismiss();
    openUpgrade("quota");
  }, [quotaDismiss, openUpgrade]);
  const onUpgrade = useCallback(() => openUpgrade("other"), [openUpgrade]);
  const onChangeModel = useCallback(() => {
    dismissChatError();
    router.push("/settings/models");
  }, [dismissChatError, router]);
  return useMemo(
    () => ({
      actionBanner, onDismissActionBanner: dismissActionBanner, showScrollToBottom, scrollAwayCount,
      onScrollToLatest: scrollToLatest, quotaNudgeVisible, quotaLabel, onQuotaUpgrade, onQuotaDismiss: quotaDismiss,
      chatError, isPaid, onUpgrade, onRetryChatError: retryChatError, onChangeModel, onDismissChatError: dismissChatError,
    }),
    [actionBanner, dismissActionBanner, showScrollToBottom, scrollAwayCount, scrollToLatest, quotaNudgeVisible,
      quotaLabel, onQuotaUpgrade, quotaDismiss, chatError, isPaid, onUpgrade, retryChatError, onChangeModel,
      dismissChatError],
  );
}

/** The chat body's props, from what the chat screen's hooks return. */
export function useChatScreenBodyProps(p: Params): ChatScreenBodyProps {
  const { styles, theme, upgrade } = p;
  const { keyboardLift } = p.keyboard;
  const { restingComposerClearance, headerInset, restingListBottomPad, emptyHeight, listBottomPad } = p.layout;
  const { listBottomPadRef } = p.scroll;
  useLayoutEffect(() => {
    listBottomPadRef.current = listBottomPad;
  }, [listBottomPadRef, listBottomPad]);

  const layout = useMemo(
    (): ChatScreenLayoutProps => ({
      styles, theme, restingComposerClearance, headerInset, restingListBottomPad, keyboardLift, emptyHeight,
    }),
    [styles, theme, restingComposerClearance, headerInset, restingListBottomPad, keyboardLift, emptyHeight],
  );
  const header = useHeader(p);
  const list = useListProps(p, header);
  const composer = useComposerProps(p);
  const chrome = useChromeProps(p);
  const { attachments } = p.wiring;
  const sheets = useSheetsProps({
    attachSheetOpen: attachments.attachSheetOpen,
    onCloseAttachSheet: attachments.closeAttachSheet,
    attachSheetLift: attachments.attachSheetLift,
    onAttachmentSource: attachments.handleAttachmentSheetSelect,
    mathScannerOpen: attachments.mathScannerOpen,
    onCloseMathScanner: attachments.closeMathScanner,
    onMathScanCaptured: attachments.handleMathScanCaptured,
    upgradeVisible: upgrade.visible,
    upgradeSource: upgrade.source,
    onCloseUpgrade: upgrade.close,
  });
  return useMemo(() => ({ layout, list, composer, chrome, sheets }), [layout, list, composer, chrome, sheets]);
}
