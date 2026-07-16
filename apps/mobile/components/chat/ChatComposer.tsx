import { memo, useMemo } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
  type ViewStyle,
} from "react-native";
import Animated, { type AnimatedStyle } from "react-native-reanimated";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { AttachmentSourceSheet, type AttachmentSource } from "@/components/AttachmentSourceSheet";
import { VoiceComposerWaveform } from "@/components/chat/VoiceComposerWaveform";
import { VoiceMicButton } from "@/components/chat/VoiceMicButton";
import { ComposerAttachmentPreview } from "@/components/ComposerAttachmentPreview";
import { SuggestedRemindersNudge } from "@/components/SuggestedRemindersNudge";
import type { PendingAttachment } from "@/lib/attachments";
import {
  composerShowsMic,
  composerShowsSend,
} from "@/lib/chatComposerLogic";
import { Theme, useTheme } from "@/lib/theme";

export const COMPOSER_HEIGHT = 88;
export const COMPOSER_IMAGE_PREVIEW_EXTRA = 84;
export const COMPOSER_FILE_PREVIEW_EXTRA = 44;

export function composerAttachmentExtra(attachment: PendingAttachment | null): number {
  if (!attachment) return 0;
  return attachment.kind === "image" ? COMPOSER_IMAGE_PREVIEW_EXTRA : COMPOSER_FILE_PREVIEW_EXTRA;
}

type Props = {
  visible: boolean;
  bottom?: number;
  paddingBottom?: number;
  animatedContainerStyle?: AnimatedStyle<ViewStyle>;
  token: string | null;
  input: string;
  onChangeInput: (text: string) => void;
  streaming: boolean;
  attachBusy: boolean;
  pendingAttachment: PendingAttachment | null;
  onRemoveAttachment: () => void;
  editingMessageId: string | null;
  onCancelEdit: () => void;
  attachSheetOpen: boolean;
  onCloseAttachSheet: () => void;
  onPickAttachment: () => void;
  onAttachmentSource: (source: AttachmentSource) => void;
  onSend: () => void;
  onStop: () => void;
  isOffline: boolean;
  voiceRecording?: boolean;
  voiceTranscribing?: boolean;
  voiceMeterLevel?: number;
  onVoicePress?: () => void;
  /** Discard in-progress recording without uploading/transcribing. */
  onVoiceCancel?: () => void;
  /** When true, parent owns absolute bottom positioning (e.g. quiz dock). */
  docked?: boolean;
};

export const ChatComposer = memo(function ChatComposer({
  visible,
  bottom,
  paddingBottom,
  animatedContainerStyle,
  token,
  input,
  onChangeInput,
  streaming,
  attachBusy,
  pendingAttachment,
  onRemoveAttachment,
  editingMessageId,
  onCancelEdit,
  attachSheetOpen,
  onCloseAttachSheet,
  onPickAttachment,
  onAttachmentSource,
  onSend,
  onStop,
  isOffline,
  voiceRecording = false,
  voiceTranscribing = false,
  voiceMeterLevel = 0.12,
  onVoicePress,
  onVoiceCancel,
  docked = false,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  if (!visible) return null;

  const hasSendableContent = Boolean(input.trim() || pendingAttachment);
  const showMic = composerShowsMic({
    voiceAvailable: Boolean(onVoicePress && token),
    voiceRecording,
    voiceTranscribing,
    hasSendableContent,
  });
  const showSend = composerShowsSend({
    voiceRecording,
    voiceTranscribing,
    hasSendableContent,
  });

  const blockStyle = docked ? s.composerDocked : s.composerBlock;
  const containerStyle = animatedContainerStyle
    ? [blockStyle, animatedContainerStyle]
    : [blockStyle, { bottom, paddingBottom }];

  return (
    <Animated.View style={containerStyle}>
      <View style={s.composerAnchor}>
        <SuggestedRemindersNudge token={token} />
        {editingMessageId ? (
          <View style={s.editBanner}>
            <Text style={s.editBannerText}>{t("chat.editing_message")}</Text>
            <Pressable onPress={onCancelEdit}>
              <Text style={s.editBannerCancel}>{t("common.cancel")}</Text>
            </Pressable>
          </View>
        ) : null}
        {attachSheetOpen ? (
          <View style={s.attachMenuFloat} pointerEvents="box-none">
            <AttachmentSourceSheet onSelect={onAttachmentSource} />
          </View>
        ) : null}
        <View style={s.composer}>
          <View style={s.inputWrap}>
            {pendingAttachment ? (
              <ComposerAttachmentPreview
                attachment={pendingAttachment}
                uploading={attachBusy}
                onRemove={onRemoveAttachment}
              />
            ) : null}
            <View style={s.inputRowMain}>
              <Pressable
                style={s.attachBtn}
                onPress={onPickAttachment}
                disabled={attachBusy || streaming}
                hitSlop={6}
                accessibilityLabel={t("chat.attach_a11y")}
              >
                <Ionicons name="attach-outline" size={22} color={theme.primary} />
              </Pressable>
              {voiceRecording || voiceTranscribing ? (
                <VoiceComposerWaveform
                  recording={voiceRecording}
                  transcribing={voiceTranscribing}
                  meterLevel={voiceMeterLevel}
                />
              ) : (
                <TextInput
                  style={s.input}
                  placeholder={t("chat.placeholder")}
                  placeholderTextColor={theme.textTertiary}
                  value={input}
                  onChangeText={onChangeInput}
                  onFocus={onCloseAttachSheet}
                  multiline
                  returnKeyType="default"
                />
              )}
              <View style={s.sendBtnSlot}>
                {streaming ? (
                  <Pressable style={s.sendBtn} onPress={onStop}>
                    <Text style={s.sendIcon}>■</Text>
                  </Pressable>
                ) : (
                  <>
                    {onVoiceCancel && voiceRecording ? (
                      <Pressable
                        style={s.voiceCancelBtn}
                        onPress={onVoiceCancel}
                        hitSlop={6}
                        accessibilityLabel={t("chat.voice_cancel_a11y")}
                        accessibilityHint={t("chat.voice_cancel_hint")}
                      >
                        <Ionicons name="close" size={18} color={theme.textSecondary} />
                      </Pressable>
                    ) : null}
                    {showMic && onVoicePress ? (
                      <VoiceMicButton
                        recording={voiceRecording}
                        transcribing={voiceTranscribing}
                        disabled={attachBusy || isOffline}
                        onPress={onVoicePress}
                      />
                    ) : null}
                    {voiceTranscribing ? (
                      <View style={[s.sendBtn, s.sendBtnDisabled]}>
                        <Text style={[s.sendIcon, s.sendIconDisabled]}>…</Text>
                      </View>
                    ) : showSend ? (
                      <Pressable
                        style={[s.sendBtn, isOffline && s.sendBtnDisabled]}
                        onPress={onSend}
                        accessibilityRole="button"
                        accessibilityLabel={t("chat.send_a11y")}
                        accessibilityHint={isOffline ? t("chat.offline_body") : undefined}
                      >
                        <Text style={[s.sendIcon, isOffline && s.sendIconDisabled]}>↑</Text>
                      </Pressable>
                    ) : null}
                  </>
                )}
              </View>
            </View>
          </View>
        </View>
      </View>
    </Animated.View>
  );
});

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    composerBlock: {
      position: "absolute",
      left: 0,
      right: 0,
      zIndex: 110,
      backgroundColor: theme.bg,
      paddingHorizontal: 12,
      paddingTop: 2,
    },
    composerDocked: {
      backgroundColor: theme.bg,
      paddingHorizontal: 12,
      paddingTop: 2,
    },
    composerAnchor: { position: "relative" },
    editBanner: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      marginHorizontal: 4,
      marginBottom: 6,
      paddingHorizontal: 12,
      paddingVertical: 8,
      borderRadius: 12,
      backgroundColor: theme.primaryLight,
    },
    editBannerText: { fontSize: 13, fontWeight: "600", color: theme.primary },
    editBannerCancel: { fontSize: 13, fontWeight: "600", color: theme.textSecondary },
    attachMenuFloat: {
      position: "absolute",
      left: 0,
      right: 14,
      bottom: "100%",
      marginBottom: 6,
      zIndex: 2,
    },
    composer: { paddingVertical: 6 },
    inputWrap: {
      backgroundColor: theme.surface,
      borderRadius: 20,
      paddingHorizontal: 12,
      paddingTop: 8,
      paddingBottom: 8,
    },
    inputRowMain: { flexDirection: "row", alignItems: "flex-end", gap: 8 },
    attachBtn: {
      width: 32,
      height: 32,
      alignItems: "center",
      justifyContent: "center",
      marginBottom: 1,
    },
    input: {
      flex: 1,
      fontSize: 16,
      color: theme.text,
      maxHeight: 100,
      paddingVertical: 0,
      minHeight: 22,
    },
    sendBtn: {
      width: 34,
      height: 34,
      borderRadius: 17,
      backgroundColor: theme.primary,
      alignItems: "center",
      justifyContent: "center",
    },
    sendBtnSlot: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "flex-end",
      gap: 6,
      minHeight: 35,
    },
    voiceCancelBtn: {
      width: 34,
      height: 34,
      borderRadius: 17,
      alignItems: "center",
      justifyContent: "center",
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      backgroundColor: theme.surface,
    },
    sendIcon: { color: theme.onPrimary, fontSize: 18, fontWeight: "700" },
    sendBtnDisabled: { backgroundColor: theme.border },
    sendIconDisabled: { color: theme.textTertiary },
  });
}
