import { memo, ReactElement, RefObject, useCallback, useEffect } from "react";
import { View, type NativeScrollEvent, type NativeSyntheticEvent, type ViewStyle } from "react-native";
import { FlashListRef, ListRenderItemInfo } from "@shopify/flash-list";
import { type AnimatedStyle } from "react-native-reanimated";

import { ActionBanner } from "@/ui/feedback/ActionBanner";
import { AttachmentSourceSheet } from "@/features/attachments/components/AttachmentSourceSheet";
import { MathEquationScanner } from "@/components/MathEquationScanner";
import { ChatComposer, type LiveTalkComposerChrome } from "@/features/chat/components/ChatComposer";
import { ChatInlineError } from "@/features/chat/components/ChatInlineError";
import { ChatMessageList } from "@/features/chat/components/ChatMessageList";
import { ChatQuotaNudge } from "@/features/chat/components/ChatQuotaNudge";
import type { ChatScreenStyles } from "@/features/chat/components/chatScreenStyles";
import { ChatScrollFab } from "@/features/chat/components/ChatScrollFab";
import type { ChatListScroll } from "@/features/chat/hooks/useChatScroll";
import { UpgradeSheet, type UpgradeSource } from "@/components/UpgradeSheet";
import { StreamingDraftProvider } from "@/contexts/StreamingDraftContext";
import { useTranslation } from "react-i18next";
import type { AttachmentSource } from "@/features/attachments/components/AttachmentSourceSheet";
import type { Message, ScanReading } from "@/lib/api";
import type { PendingAttachment } from "@/features/attachments/model/attachments";
import type { ReadBackSubject } from "@/lib/scanner/readBack";
import type { ScannerSubject } from "@/lib/scanner/subjects";
import type { ResolvedChatError } from "@/features/chat/model/errorMessage";
import type { IconName } from "@/ui/icons/names";
import type { Theme } from "@/lib/theme";

export interface ChatScreenLayoutProps {
  styles: ChatScreenStyles;
  theme: Theme;
  drawerOpen: boolean;
  composerClearance: number;
  headerInset: number;
  listBottomPad: number;
  emptyHeight: number;
}

export interface ChatScreenListProps {
  listRef: RefObject<FlashListRef<Message> | null>;
  messages: Message[];
  hasMoreOlder: boolean;
  loadingOlder: boolean;
  chatLoading: boolean;
  routeChatId?: string;
  renderItem: (info: ListRenderItemInfo<Message>) => ReactElement | null;
  onLoadOlder: () => void;
  onScroll: (event: NativeSyntheticEvent<NativeScrollEvent>) => void;
  onScrollEnd: () => void;
  scroll?: ChatListScroll;
  header: ReactElement | null;
}

export interface ChatScreenComposerProps {
  animatedStyle?: AnimatedStyle<ViewStyle>;
  streaming: boolean;
  attachPicking: boolean;
  sendBusy: boolean;
  sendStatus?: string;
  pendingAttachment: PendingAttachment | null;
  onRemoveAttachment: () => void;
  onPickAttachment: () => void;
  onOpenMathScanner?: () => void;
  onMathChromeHeightChange?: (height: number) => void;
  onInputFrameExtraChange?: (extra: number) => void;
  onSend: (text?: string) => void;
  onStop: () => void;
  isOffline: boolean;
  voiceAvailable: boolean;
  voiceRecording: boolean;
  voiceTranscribing: boolean;
  voiceMeterLevel: number;
  onVoicePress?: () => void;
  onCancelVoice?: () => void;
  onLiveTalkPress?: () => void;
  liveTalkSession?: LiveTalkComposerChrome | null;
}

export interface ChatScreenChromeProps {
  actionBanner: {
    message: string;
    icon?: IconName;
  } | null;
  onDismissActionBanner: () => void;
  showScrollToBottom: boolean;
  scrollAwayCount: number;
  onScrollToLatest: () => void;
  quotaNudgeVisible: boolean;
  quotaUsedPct: number;
  onQuotaUpgrade: () => void;
  onQuotaDismiss: () => void;
  chatError: ResolvedChatError | null;
  isPaid: boolean;
  onUpgrade: () => void;
  onRetryChatError: () => void;
  onChangeModel: () => void;
  onDismissChatError: () => void;
}

export interface ChatScreenSheetsProps {
  attachSheetOpen: boolean;
  onCloseAttachSheet: () => void;
  onAttachmentSource: (source: AttachmentSource) => void;
  mathScannerOpen: boolean;
  onCloseMathScanner: () => void;
  onMathScanCaptured: (
    pending: PendingAttachment,
    subject: ScannerSubject,
    confirmedReading?: string,
  ) => void;
  onReadScan: (
    scan: PendingAttachment,
    subject: ReadBackSubject,
    signal: AbortSignal,
  ) => Promise<ScanReading | { error: string } | null>;
  onMathScanSolve: (reading: string, subject: ScannerSubject) => void;
  upgradeVisible: boolean;
  /** Where the paywall was opened from (analytics only). */
  upgradeSource?: UpgradeSource;
  onCloseUpgrade: () => void;
}

export interface ChatScreenBodyProps {
  layout: ChatScreenLayoutProps;
  list: ChatScreenListProps;
  composer: ChatScreenComposerProps;
  chrome: ChatScreenChromeProps;
  sheets: ChatScreenSheetsProps;
}

export const ChatScreenBody = memo(function ChatScreenBody({
  layout,
  list,
  composer,
  chrome,
  sheets,
}: ChatScreenBodyProps) {
  const { t } = useTranslation();
  const { styles: s, drawerOpen } = layout;
  const { messages } = list;
  const { liveTalkSession, onSend } = composer;
  const { mathScannerOpen, onCloseMathScanner } = sheets;
  const handleComposerSend = useCallback(
    (text?: string) => {
      liveTalkSession?.onYield();
      onSend(text);
    },
    [liveTalkSession, onSend],
  );

  useEffect(() => {
    if (drawerOpen && mathScannerOpen) onCloseMathScanner();
  }, [drawerOpen, mathScannerOpen, onCloseMathScanner]);

  return (
    <View style={s.container}>
      <StreamingDraftProvider>
        <ChatMessageList
          listRef={list.listRef}
          messages={messages}
          headerInset={layout.headerInset}
          listBottomPad={layout.listBottomPad}
          hasMoreOlder={list.hasMoreOlder}
          loadingOlder={list.loadingOlder}
          chatLoading={list.chatLoading}
          routeChatId={list.routeChatId}
          emptyHeight={layout.emptyHeight}
          renderItem={list.renderItem}
          onLoadOlder={list.onLoadOlder}
          onScroll={list.onScroll}
          onScrollEnd={list.onScrollEnd}
          scroll={list.scroll}
          header={list.header}
        />
      </StreamingDraftProvider>

      <ChatComposer
        visible={!drawerOpen}
        animatedContainerStyle={composer.animatedStyle}
        streaming={composer.streaming}
        attachPicking={composer.attachPicking}
        sendBusy={composer.sendBusy}
        sendStatus={composer.sendStatus}
        pendingAttachment={composer.pendingAttachment}
        onRemoveAttachment={composer.onRemoveAttachment}
        onCloseAttachSheet={sheets.onCloseAttachSheet}
        onPickAttachment={composer.onPickAttachment}
        onSend={handleComposerSend}
        onStop={composer.onStop}
        isOffline={composer.isOffline}
        voiceAvailable={composer.voiceAvailable}
        voiceRecording={composer.voiceRecording}
        voiceTranscribing={composer.voiceTranscribing}
        voiceMeterLevel={composer.voiceMeterLevel}
        onVoicePress={composer.onVoicePress}
        onCancelVoice={composer.onCancelVoice}
        onLiveTalkPress={composer.onLiveTalkPress}
        liveTalkChrome={composer.liveTalkSession}
        onOpenMathScanner={composer.onOpenMathScanner}
        onMathChromeHeightChange={composer.onMathChromeHeightChange}
        onInputFrameExtraChange={composer.onInputFrameExtraChange}
      />

      <ChatOverlays
        layout={layout}
        chrome={chrome}
        sheets={sheets}
        onStop={composer.onStop}
        quotaUpgradeLabel={t("chat.quota_nudge_cta")}
      />
    </View>
  );
});

type ChatOverlaysProps = {
  layout: ChatScreenLayoutProps;
  chrome: ChatScreenChromeProps;
  sheets: ChatScreenSheetsProps;
  onStop: () => void;
  quotaUpgradeLabel: string;
};

const ChatOverlays = memo(function ChatOverlays({
  layout,
  chrome,
  sheets,
  onStop,
  quotaUpgradeLabel,
}: ChatOverlaysProps) {
  const { styles, theme, drawerOpen, composerClearance } = layout;

  return (
    <>
      <ChatScrollFab
        visible={!drawerOpen && chrome.showScrollToBottom}
        bottomOffset={composerClearance + 8}
        scrollAwayCount={chrome.scrollAwayCount}
        onPress={chrome.onScrollToLatest}
      />

      {chrome.quotaNudgeVisible && !chrome.chatError ? (
        <ChatQuotaNudge
          styles={styles}
          theme={theme}
          bottomOffset={composerClearance + 8}
          usedPct={chrome.quotaUsedPct}
          onUpgrade={chrome.onQuotaUpgrade}
          onDismiss={chrome.onQuotaDismiss}
        />
      ) : null}

      <ChatInlineError
        error={chrome.chatError}
        bottom={composerClearance + 8}
        upgradeLabel={!chrome.isPaid ? quotaUpgradeLabel : undefined}
        onUpgrade={!chrome.isPaid ? chrome.onUpgrade : undefined}
        onStop={onStop}
        onRetry={chrome.onRetryChatError}
        onChangeModel={chrome.onChangeModel}
        onDismiss={chrome.onDismissChatError}
      />

      <ActionBanner
        message={chrome.actionBanner?.message ?? null}
        icon={chrome.actionBanner?.icon}
        bottomOffset={composerClearance + 12}
        onDismiss={chrome.onDismissActionBanner}
      />

      <AttachmentSourceSheet
        visible={sheets.attachSheetOpen && !drawerOpen}
        onClose={sheets.onCloseAttachSheet}
        onSelect={sheets.onAttachmentSource}
      />

      <MathEquationScanner
        visible={sheets.mathScannerOpen}
        onClose={sheets.onCloseMathScanner}
        onCaptured={sheets.onMathScanCaptured}
        onReadScan={sheets.onReadScan}
        onSolveReading={sheets.onMathScanSolve}
      />

      <UpgradeSheet
        visible={sheets.upgradeVisible}
        source={sheets.upgradeSource}
        onClose={sheets.onCloseUpgrade}
      />
    </>
  );
});
