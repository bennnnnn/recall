import { ReactElement, RefObject, useMemo } from "react";
import { View, type NativeScrollEvent, type NativeSyntheticEvent, type ViewStyle } from "react-native";
import { FlashListRef, ListRenderItemInfo } from "@shopify/flash-list";
import { type AnimatedStyle } from "react-native-reanimated";

import { ActionBanner } from "@/components/ActionBanner";
import { AttachmentSourceSheet } from "@/components/AttachmentSourceSheet";
import { MathEquationScanner } from "@/components/MathEquationScanner";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { ChatInlineError } from "@/components/chat/ChatInlineError";
import { ChatMessageList } from "@/components/chat/ChatMessageList";
import { ChatQuotaNudge } from "@/components/chat/ChatQuotaNudge";
import type { ChatScreenStyles } from "@/components/chat/chatScreenStyles";
import { ChatScrollFab } from "@/components/chat/ChatScrollFab";
import { UpgradeSheet } from "@/components/UpgradeSheet";
import { StreamingDraftProvider } from "@/contexts/StreamingDraftContext";
import { useTranslation } from "react-i18next";
import type { AttachmentSource } from "@/components/AttachmentSourceSheet";
import type { Message } from "@/lib/api";
import type { PendingAttachment } from "@/lib/attachments";
import type { ResolvedChatError } from "@/lib/chatErrorMessage";
import { type IoniconName } from "@/lib/icons";
import { messagesLookLikeMath } from "@/lib/math/mathComposerIntent";
import type { Theme } from "@/lib/theme";

export type ChatScreenBodyProps = {
  styles: ChatScreenStyles;
  theme: Theme;
  token: string;
  drawerOpen: boolean;
  composerClearance: number;
  actionBanner: {
    message: string;
    icon?: IoniconName;
  } | null;
  onDismissActionBanner: () => void;
  listRef: RefObject<FlashListRef<Message> | null>;
  messages: Message[];
  headerInset: number;
  listBottomPad: number;
  hasMoreOlder: boolean;
  loadingOlder: boolean;
  chatLoading: boolean;
  routeChatId?: string;
  emptyHeight: number;
  renderItem: (info: ListRenderItemInfo<Message>) => ReactElement | null;
  onLoadOlder: () => void;
  onScroll: (event: NativeSyntheticEvent<NativeScrollEvent>) => void;
  onScrollEnd: () => void;
  onSelectStarter: (prompt: string, chatId?: string) => void;
  listHeader: ReactElement | null;
  showScrollToBottom: boolean;
  scrollAwayCount: number;
  onScrollToLatest: () => void;
  attachSheetOpen: boolean;
  onCloseAttachSheet: () => void;
  quotaNudgeVisible: boolean;
  quotaUsedPct: number;
  onQuotaUpgrade: () => void;
  onQuotaDismiss: () => void;
  chatError: ResolvedChatError | null;
  isPro: boolean;
  onUpgrade: () => void;
  onRetryChatError: () => void;
  onChangeModel: () => void;
  onDismissChatError: () => void;
  composerAnimatedStyle?: AnimatedStyle<ViewStyle>;
  streaming: boolean;
  attachBusy: boolean;
  attachPicking: boolean;
  sendBusy: boolean;
  pendingAttachment: PendingAttachment | null;
  onRemoveAttachment: () => void;
  editingMessageId: string | null;
  onCancelEdit: () => void;
  onPickAttachment: () => void;
  onAttachmentSource: (source: AttachmentSource) => void;
  mathScannerOpen: boolean;
  onCloseMathScanner: () => void;
  onMathScanCaptured: (pending: PendingAttachment) => void;
  onOpenMathScanner?: () => void;
  onMathChromeHeightChange?: (height: number) => void;
  onSend: (text?: string) => void;
  onStop: () => void;
  isOffline: boolean;
  voiceAvailable: boolean;
  voiceRecording: boolean;
  voiceTranscribing: boolean;
  voiceMeterLevel: number;
  onVoicePress?: () => void;
  upgradeVisible: boolean;
  onCloseUpgrade: () => void;
  listFooter?: ReactElement | null;
  hideHomeStarters?: boolean;
};

export function ChatScreenBody({
  styles: s,
  theme,
  token,
  drawerOpen,
  composerClearance,
  actionBanner,
  onDismissActionBanner,
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
  onScroll,
  onScrollEnd,
  onSelectStarter,
  listHeader,
  showScrollToBottom,
  scrollAwayCount,
  onScrollToLatest,
  attachSheetOpen,
  onCloseAttachSheet,
  quotaNudgeVisible,
  quotaUsedPct,
  onQuotaUpgrade,
  onQuotaDismiss,
  chatError,
  isPro,
  onUpgrade,
  onRetryChatError,
  onChangeModel,
  onDismissChatError,
  composerAnimatedStyle,
  streaming,
  attachBusy,
  attachPicking,
  sendBusy,
  pendingAttachment,
  onRemoveAttachment,
  editingMessageId,
  onCancelEdit,
  onPickAttachment,
  onAttachmentSource,
  mathScannerOpen,
  onCloseMathScanner,
  onMathScanCaptured,
  onOpenMathScanner,
  onMathChromeHeightChange,
  onSend,
  onStop,
  isOffline,
  voiceAvailable,
  voiceRecording,
  voiceTranscribing,
  voiceMeterLevel,
  onVoicePress,
  upgradeVisible,
  onCloseUpgrade,
  listFooter = null,
  hideHomeStarters = false,
}: ChatScreenBodyProps) {
  const { t } = useTranslation();
  const mathContext = useMemo(
    () => messagesLookLikeMath(messages.map((m) => m.content)),
    [messages],
  );

  return (
    <View style={s.container}>
      <ActionBanner
        message={actionBanner?.message ?? null}
        icon={actionBanner?.icon}
        bottomOffset={composerClearance + 12}
        onDismiss={onDismissActionBanner}
      />
      <StreamingDraftProvider>
        <ChatMessageList
          listRef={listRef}
          messages={messages}
          headerInset={headerInset}
          listBottomPad={listBottomPad}
          hasMoreOlder={hasMoreOlder}
          loadingOlder={loadingOlder}
          chatLoading={chatLoading}
          routeChatId={routeChatId}
          emptyHeight={emptyHeight}
          renderItem={renderItem}
          onLoadOlder={onLoadOlder}
          onScroll={onScroll}
          onScrollEnd={onScrollEnd}
          onSelectStarter={onSelectStarter}
          header={listHeader}
          hideHomeStarters={hideHomeStarters}
          listFooter={listFooter}
          streamActive={streaming}
        />
      </StreamingDraftProvider>

      <ChatScrollFab
        visible={!drawerOpen && showScrollToBottom}
        bottomOffset={composerClearance + 8}
        scrollAwayCount={scrollAwayCount}
        onPress={onScrollToLatest}
      />

      {quotaNudgeVisible && !chatError ? (
        <ChatQuotaNudge
          styles={s}
          theme={theme}
          bottomOffset={composerClearance + 8}
          usedPct={quotaUsedPct}
          onUpgrade={onQuotaUpgrade}
          onDismiss={onQuotaDismiss}
        />
      ) : null}

      <ChatInlineError
        error={chatError}
        bottom={composerClearance + 8}
        upgradeLabel={!isPro ? t("chat.quota_nudge_cta") : undefined}
        onUpgrade={!isPro ? onUpgrade : undefined}
        onStop={onStop}
        onRetry={onRetryChatError}
        onChangeModel={onChangeModel}
        onDismiss={onDismissChatError}
      />

      <ChatComposer
        visible={!drawerOpen}
        animatedContainerStyle={composerAnimatedStyle}
        token={token}
        streaming={streaming}
        attachBusy={attachBusy}
            attachPicking={attachPicking}
            sendBusy={sendBusy}
        pendingAttachment={pendingAttachment}
        onRemoveAttachment={onRemoveAttachment}
        editingMessageId={editingMessageId}
        onCancelEdit={onCancelEdit}
        onCloseAttachSheet={onCloseAttachSheet}
        onPickAttachment={onPickAttachment}
        onSend={onSend}
        onStop={onStop}
        isOffline={isOffline}
        voiceAvailable={voiceAvailable}
        voiceRecording={voiceRecording}
        voiceTranscribing={voiceTranscribing}
        voiceMeterLevel={voiceMeterLevel}
        onVoicePress={onVoicePress}
        onOpenMathScanner={onOpenMathScanner}
        onMathChromeHeightChange={onMathChromeHeightChange}
        mathContext={mathContext}
      />

      <AttachmentSourceSheet
        visible={attachSheetOpen && !drawerOpen}
        onClose={onCloseAttachSheet}
        onSelect={onAttachmentSource}
      />

      <MathEquationScanner
        visible={mathScannerOpen && !drawerOpen}
        onClose={onCloseMathScanner}
        onCaptured={onMathScanCaptured}
      />

      <UpgradeSheet visible={upgradeVisible} onClose={onCloseUpgrade} />
    </View>
  );
}
