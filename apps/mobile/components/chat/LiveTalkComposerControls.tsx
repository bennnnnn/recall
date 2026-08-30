import { Pressable, StyleSheet, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import {
  liveTalkSpeakerA11yKey,
  liveTalkSpeakerAction,
  type LiveTalkPhase,
} from "@/lib/liveTalkLogic";
import { useTheme } from "@/lib/theme";

type Props = {
  phase: LiveTalkPhase;
  onSpeakerPress: () => void;
  onClose: () => void;
};

/** Speaker + close, same row as the composer (ChatGPT voice chrome). */
export function LiveTalkComposerControls({ phase, onSpeakerPress, onClose }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const speakerAction = liveTalkSpeakerAction(phase);
  const speakerA11y = liveTalkSpeakerA11yKey(phase);

  return (
    <View style={styles.row}>
      <Pressable
        onPress={onSpeakerPress}
        style={[styles.round, { borderColor: theme.composerBorder, backgroundColor: theme.inputBg }]}
        accessibilityRole="button"
        accessibilityLabel={t(speakerA11y)}
        testID="live-talk-speaker"
      >
        <Icon
          name={speakerAction === "pause" ? "volume-high" : "volume-high-outline"}
          size={26}
          color={theme.text}
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
