import { ReactElement, RefObject } from "react";
import { View, type NativeScrollEvent, type NativeSyntheticEvent, type ViewStyle } from "react-native";
import { FlashListRef, ListRenderItemInfo } from "@shopify/flash-list";
import { Ionicons } from "@expo/vector-icons";
import { type AnimatedStyle } from "react-native-reanimated";

import { ActionBanner } from "@/components/ActionBanner";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { ChatInlineError } from "@/components/chat/ChatInlineError";
import { ChatMessageList } from "@/components/chat/ChatMessageList";
import { ChatQuotaNudge } from "@/components/chat/ChatQuotaNudge";
import type { ChatScreenStyles } from "@/components/chat/chatScreenStyles";
import { ChatScrollFab } from "@/components/chat/ChatScrollFab";
import { ComposerPickerBackdrop } from "@/components/chat/ComposerPickerBackdrop";
import { UpgradeSheet } from "@/components/UpgradeSheet";
import { StreamingDraftProvider } from "@/contexts/StreamingDraftContext";
import { useTranslation } from "react-i18next";
import type { AttachmentSource } from "@/components/AttachmentSourceSheet";
import type { Message } from "@/lib/api";
import type { PendingAttachment } from "@/lib/attachments";
import type { ResolvedChatError } from "@/lib/chatErrorMessage";
import type { Theme } from "@/lib/theme";

type ModelOption = { id: string; label: string };

export type ChatScreenBodyProps = {
  styles: ChatScreenStyles;
  theme: Theme;
  token: string;
  drawerOpen: boolean;
  composerClearance: number;
  actionBanner: {
    message: string;
    icon?: keyof typeof Ionicons.glyphMap;
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
  onSelectStarter: (prompt: string) => void;
  listHeader: ReactElement | null;
  showScrollToBottom: boolean;
  scrollAwayCount: number;
  onScrollToLatest: () => void;
  showModelPicker: boolean;
  attachSheetOpen: boolean;
  onCloseComposerPickers: () => void;
  quotaNudgeVisible: boolean;
  quotaUsedPct: number;
  onQuotaUpgrade: () => void;
  onQuotaDismiss: () => void;
  chatError: ResolvedChatError | null;
  isPro: boolean;
  onUpgrade: () => void;
  onDismissChatError: () => void;
  composerAnimatedStyle?: AnimatedStyle<ViewStyle>;
  input: string;
  onChangeInput: (text: string) => void;
  streaming: boolean;
  attachBusy: boolean;
  pendingAttachment: PendingAttachment | null;
  onRemoveAttachment: () => void;
  editingMessageId: string | null;
  onCancelEdit: () => void;
  modelOptions: ModelOption[];
  selectedModel: string;
  selectedModelLabel: string;
  onToggleModelPicker: () => void;
  onSelectModel: (id: string) => void;
  onPickAttachment: () => void;
  onAttachmentSource: (source: AttachmentSource) => void;
  onSend: () => void;
  onStop: () => void;
  isOffline: boolean;
  voiceRecording: boolean;
  voiceTranscribing: boolean;
  voiceMeterLevel: number;
  onVoicePress?: () => void;
  upgradeVisible: boolean;
  onCloseUpgrade: () => void;
  quizPanel?: ReactElement | null;
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
  showModelPicker,
  attachSheetOpen,
  onCloseComposerPickers,
  quotaNudgeVisible,
  quotaUsedPct,
  onQuotaUpgrade,
  onQuotaDismiss,
  chatError,
  isPro,
  onUpgrade,
  onDismissChatError,
  composerAnimatedStyle,
  input,
  onChangeInput,
  streaming,
  attachBusy,
  pendingAttachment,
  onRemoveAttachment,
  editingMessageId,
  onCancelEdit,
  modelOptions,
  selectedModel,
  selectedModelLabel,
  onToggleModelPicker,
  onSelectModel,
  onPickAttachment,
  onAttachmentSource,
  onSend,
  onStop,
  isOffline,
  voiceRecording,
  voiceTranscribing,
  voiceMeterLevel,
  onVoicePress,
  upgradeVisible,
  onCloseUpgrade,
  quizPanel,
}: ChatScreenBodyProps) {
  const { t } = useTranslation();

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
        />
      </StreamingDraftProvider>

      <ChatScrollFab
        visible={!drawerOpen && showScrollToBottom}
        bottomOffset={composerClearance + 8}
        scrollAwayCount={scrollAwayCount}
        onPress={onScrollToLatest}
      />

      <ComposerPickerBackdrop
        visible={(showModelPicker || attachSheetOpen) && !drawerOpen}
        onClose={onCloseComposerPickers}
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
        onDismiss={onDismissChatError}
      />

      {quizPanel}

      <ChatComposer
        visible={!drawerOpen}
        animatedContainerStyle={composerAnimatedStyle}
        token={token}
        input={input}
        onChangeInput={onChangeInput}
        streaming={streaming}
        attachBusy={attachBusy}
        pendingAttachment={pendingAttachment}
        onRemoveAttachment={onRemoveAttachment}
        editingMessageId={editingMessageId}
        onCancelEdit={onCancelEdit}
        showModelPicker={showModelPicker}
        attachSheetOpen={attachSheetOpen}
        modelOptions={modelOptions}
        selectedModel={selectedModel}
        selectedModelLabel={selectedModelLabel}
        onToggleModelPicker={onToggleModelPicker}
        onSelectModel={onSelectModel}
        onClosePickers={onCloseComposerPickers}
        onPickAttachment={onPickAttachment}
        onAttachmentSource={onAttachmentSource}
        onSend={onSend}
        onStop={onStop}
        isOffline={isOffline}
        voiceRecording={voiceRecording}
        voiceTranscribing={voiceTranscribing}
        voiceMeterLevel={voiceMeterLevel}
        onVoicePress={onVoicePress}
      />

      <UpgradeSheet visible={upgradeVisible} onClose={onCloseUpgrade} />
    </View>
  );
}
