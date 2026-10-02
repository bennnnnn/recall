import { Pressable, StyleSheet, View } from "react-native";
import Svg, { Rect } from "react-native-svg";
import { useTranslation } from "react-i18next";

import { COMPOSER_CONTROL_SIZE } from "@/lib/chat/composerLogic";
import { lightTheme, useTheme } from "@/lib/theme";
import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";

/** Stop mark with softened corners so it sits with the other composer icons. */
function RoundedStop({ size, color }: { size: number; color: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <Rect testID="voice-stop-mark" x="4.5" y="4.5" width="15" height="15" rx="5" fill={color} />
    </Svg>
  );
}

type Props = {
  recording: boolean;
  transcribing: boolean;
  disabled?: boolean;
  onPress: () => void;
};

export function VoiceMicButton({ recording, transcribing, disabled, onPress }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();

  return (
    <Pressable
      style={[styles.hit, disabled && styles.dim]}
      onPress={onPress}
      disabled={disabled || transcribing}
      hitSlop={8}
      accessibilityRole="button"
      accessibilityLabel={t("chat.voice_a11y")}
      accessibilityHint={recording ? t("chat.voice_stop_hint") : t("chat.voice_start_hint")}
      accessibilityState={{ disabled: Boolean(disabled || transcribing), busy: transcribing }}
    >
      <View
        testID="voice-mic-surface"
        style={[styles.btn, recording && styles.stopDisc]}
      >
        {recording ? (
          <RoundedStop size={IconSize.md} color={lightTheme.text} />
        ) : (
          <Icon name="mic" size={IconSize.md} color={theme.text} testID="voice-mic-icon" />
        )}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  hit: {
    width: COMPOSER_CONTROL_SIZE,
    height: COMPOSER_CONTROL_SIZE,
    alignItems: "center",
    justifyContent: "center",
  },
  dim: { opacity: 0.55 },
  btn: {
    width: COMPOSER_CONTROL_SIZE,
    height: COMPOSER_CONTROL_SIZE,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "transparent",
  },
  stopDisc: {
    backgroundColor: lightTheme.bg,
    borderRadius: COMPOSER_CONTROL_SIZE / 2,
  },
});
