import { StyleSheet, View } from "react-native";
import { useTranslation } from "react-i18next";

import { IconButton } from "@/ui/controls/IconButton";
import { liveTalkMuteA11yKey } from "@/features/speech/model/liveTalkLogic";
import { useTheme } from "@/lib/theme";
import { IconSize } from "@/ui/icons/sizes";
import { Space } from "@/lib/space";
import { Radius } from "@/lib/radius";

type Props = {
  muted: boolean;
  onMutePress: () => void;
  onClose: () => void;
};

/**
 * Mute and end, a centred pair where the composer row sits; the composer is not drawn
 * during a call. Red mute means Recall cannot hear you. Only end (✕) ends the call.
 */
export function LiveTalkCallControls({ muted, onMutePress, onClose }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();

  return (
    <View style={styles.row} testID="live-talk-controls">
      <IconButton
        onPress={onMutePress}
        style={[
          styles.round,
          muted
            ? { backgroundColor: theme.danger, borderColor: theme.danger }
            : { backgroundColor: theme.inputBg, borderColor: theme.borderStrong },
        ]}
        accessibilityLabel={t(liveTalkMuteA11yKey(muted))}
        testID="live-talk-mute"
        name={muted ? "mic-off" : "mic"}
        size={IconSize.md}
        color={muted ? theme.onPrimary : theme.text}
      />
      <IconButton
        onPress={onClose}
        style={[styles.round, { backgroundColor: theme.text }]}
        accessibilityLabel={t("chat.live_talk_close_a11y")}
        testID="live-talk-close"
        name="close"
        size={IconSize.md}
        color={theme.onPrimary}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: Space.xl,
  },
  round: {
    width: 52,
    height: 52,
    borderRadius: Radius.full,
    borderWidth: 1,
    borderColor: "transparent",
    alignItems: "center",
    justifyContent: "center",
  },
});
