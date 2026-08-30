import { Pressable, StyleSheet, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { liveTalkMuteA11yKey } from "@/lib/liveTalkLogic";
import { useTheme } from "@/lib/theme";

type Props = {
  muted: boolean;
  onMutePress: () => void;
  onClose: () => void;
};

/** Mic mute + close, same row as the composer. Red means the model cannot hear you. */
export function LiveTalkComposerControls({ muted, onMutePress, onClose }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();

  return (
    <View style={styles.row}>
      <Pressable
        onPress={onMutePress}
        style={[
          styles.round,
          muted
            ? { backgroundColor: theme.danger, borderColor: theme.danger }
            : { backgroundColor: theme.inputBg, borderColor: theme.composerBorder },
        ]}
        accessibilityRole="button"
        accessibilityLabel={t(liveTalkMuteA11yKey(muted))}
        testID="live-talk-mute"
      >
        <Icon
          name={muted ? "mic-off" : "mic-outline"}
          size={24}
          color={muted ? theme.onPrimary : theme.text}
        />
      </Pressable>
      <Pressable
        onPress={onClose}
        style={[styles.round, { backgroundColor: theme.text }]}
        accessibilityRole="button"
        accessibilityLabel={t("chat.live_talk_close_a11y")}
        testID="live-talk-close"
      >
        <Icon name="close" size={22} color={theme.onPrimary} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingBottom: 2,
  },
  round: {
    width: 52,
    height: 52,
    borderRadius: 26,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "transparent",
    alignItems: "center",
    justifyContent: "center",
  },
});
