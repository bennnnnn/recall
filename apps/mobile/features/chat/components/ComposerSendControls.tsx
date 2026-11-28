import { ActivityIndicator, Pressable, View } from "react-native";
import { useTranslation } from "react-i18next";

import type { makeChatComposerStyles } from "@/features/chat/components/chatComposerStyles";
import { useSendUpload } from "@/features/chat/hooks/useSendUpload";
import { COMPOSER_CONTROL_SIZE } from "@/features/chat/model/composerLogic";
import { LiveTalkButton } from "@/features/speech/components/LiveTalkButton";
import { VoiceMicButton } from "@/features/speech/components/VoiceMicButton";
import { useTheme } from "@/lib/theme";
import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";

type Props = {
  s: ReturnType<typeof makeChatComposerStyles>;
  streaming: boolean;
  onStop: () => void;
  onSend: () => void;
  showSend: boolean;
  sendBusy: boolean;
  isOffline: boolean;
  /** A free plan's messages are used up for today. */
  quotaBlocked?: boolean;
  /** The draft is longer than a message may be: Send waits (the composer's note says why). */
  tooLong?: boolean;
  /** A picked file is still being prepared: send, the mic and live talk wait for it. */
  attachBusy: boolean;
  showMic: boolean;
  voiceRecording: boolean;
  voiceTranscribing: boolean;
  onVoicePress?: () => void;
  onLiveTalkPress?: () => void;
};

/** Stop while a reply streams; otherwise mic, live talk or send, whichever the draft calls for. */
export function ComposerSendControls({
  s,
  streaming,
  onStop,
  onSend,
  showSend,
  sendBusy,
  isOffline,
  quotaBlocked = false,
  tooLong = false,
  attachBusy,
  showMic,
  voiceRecording,
  voiceTranscribing,
  onVoicePress,
  onLiveTalkPress,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const upload = useSendUpload();
  if (sendBusy && upload) {
    // A file on its way: Cancel stops it and gives the draft back.
    return (
      <View style={s.sendBtnSlot}>
        <Pressable
          style={s.sendBtn}
          onPress={upload.cancel}
          hitSlop={6}
          accessibilityRole="button"
          accessibilityLabel={t("chat.cancel_upload")}
          testID="composer-cancel-upload"
        >
          <Icon name="stop" size={IconSize.xxs} color={theme.onPrimary} />
        </Pressable>
      </View>
    );
  }
  if (streaming) {
    return (
      <View style={s.sendBtnSlot}>
        <Pressable
          style={s.sendBtn}
          onPress={onStop}
          hitSlop={6}
          accessibilityRole="button"
          accessibilityLabel={t("chat.stop_a11y")}
        >
          <Icon name="stop" size={IconSize.xxs} color={theme.onPrimary} />
        </Pressable>
      </View>
    );
  }
  const voiceActive = voiceRecording || voiceTranscribing;
  const sendDisabled = isOffline || sendBusy || attachBusy || quotaBlocked || tooLong;
  return (
    <View style={s.sendBtnSlot}>
      {showMic && onVoicePress ? (
        <VoiceMicButton
          size={COMPOSER_CONTROL_SIZE}
          recording={voiceRecording}
          transcribing={voiceTranscribing}
          disabled={attachBusy || sendBusy || isOffline}
          onPress={onVoicePress}
        />
      ) : null}
      {onLiveTalkPress && !voiceActive && !showSend && !sendBusy ? (
        <LiveTalkButton size={COMPOSER_CONTROL_SIZE} disabled={attachBusy || isOffline} onPress={onLiveTalkPress} />
      ) : null}
      {showSend || sendBusy ? (
        <Pressable
          style={[s.sendBtn, sendDisabled && s.sendBtnDisabled]}
          onPress={onSend}
          disabled={sendDisabled}
          hitSlop={6}
          accessibilityRole="button"
          accessibilityLabel={sendBusy ? t("chat.sending") : t("chat.send_a11y")}
          accessibilityHint={isOffline ? t("chat.offline_body") : quotaBlocked ? t("chat.quota_exceeded_free") : undefined}
          accessibilityState={{ disabled: sendDisabled, busy: sendBusy }}
        >
          {sendBusy ? (
            <ActivityIndicator size="small" color={theme.textTertiary} />
          ) : (
            <Icon
              name="arrow-up"
              size={IconSize.sm}
              color={isOffline || quotaBlocked || tooLong ? theme.textTertiary : theme.onPrimary}
            />
          )}
        </Pressable>
      ) : null}
    </View>
  );
}
