import { useMemo } from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { LiveTalkOrb } from "@/components/chat/LiveTalkOrb";
import {
  liveTalkCanTakeFloor,
  liveTalkHintKey,
  liveTalkOrbA11yKey,
  type LiveTalkPhase,
} from "@/lib/liveTalkLogic";
import { useReduceMotion } from "@/lib/motion";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  visible: boolean;
  phase: LiveTalkPhase;
  meterLevel: number;
  recording: boolean;
  onClose: () => void;
  onToggle: () => void;
  onInterrupt: () => void;
};

export function LiveTalkOverlay({
  visible,
  phase,
  meterLevel,
  recording,
  onClose,
  onToggle,
  onInterrupt,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const takeFloor = liveTalkCanTakeFloor(phase);
  const hint = t(liveTalkHintKey(phase));

  return (
    <Modal
      visible={visible}
      animationType="fade"
      presentationStyle="fullScreen"
      onRequestClose={onClose}
    >
      <View style={[s.root, { paddingTop: insets.top + 12, paddingBottom: insets.bottom + 16 }]}>
        <View style={s.center}>
          <Pressable
            onPress={onToggle}
            accessibilityRole="button"
            accessibilityLabel={t(liveTalkOrbA11yKey(phase))}
            testID="live-talk-orb"
          >
            <LiveTalkOrb
              theme={theme}
              phase={phase === "paused" ? "idle" : phase}
              meterLevel={meterLevel}
              recording={recording}
              reduceMotion={reduceMotion}
            />
          </Pressable>
          <Text style={s.hint}>{hint}</Text>
        </View>

        <View style={s.bottom}>
          {takeFloor ? (
            <Pressable
              onPress={onInterrupt}
              style={[s.pill, s.pillPress, { backgroundColor: theme.inputBg, borderColor: theme.composerBorder }]}
              accessibilityRole="button"
              accessibilityLabel={t("chat.live_talk_interrupt_a11y")}
            >
              <Icon name="mic-outline" size={22} color={theme.text} />
              <Text style={s.pillAction}>{t("chat.live_talk_interrupt")}</Text>
            </Pressable>
          ) : (
            <View
              style={[s.pill, { backgroundColor: theme.inputBg, borderColor: theme.composerBorder }]}
            >
              <Icon name="add-outline" size={22} color={theme.text} />
              <Text style={s.pillText}>{t("chat.live_talk_ask")}</Text>
            </View>
          )}
          <Pressable
            onPress={onClose}
            style={s.closeBtn}
            accessibilityRole="button"
            accessibilityLabel={t("chat.live_talk_close_a11y")}
          >
            <Icon name="close" size={22} color={theme.onPrimary} />
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    root: {
      flex: 1,
      backgroundColor: theme.bg,
      paddingHorizontal: 16,
    },
    center: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      gap: 20,
    },
    hint: {
      ...Type.secondary,
      color: theme.textSecondary,
      textAlign: "center",
    },
    bottom: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      paddingHorizontal: 4,
    },
    pill: {
      flex: 1,
      height: 52,
      borderRadius: 26,
      borderWidth: StyleSheet.hairlineWidth,
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: 16,
      gap: 8,
    },
    pillPress: {
      minHeight: 52,
    },
    pillText: {
      ...Type.body,
      color: theme.textTertiary,
    },
    pillAction: {
      ...Type.body,
      fontWeight: "600",
      color: theme.text,
    },
    closeBtn: {
      width: 52,
      height: 52,
      borderRadius: 26,
      backgroundColor: theme.text,
      alignItems: "center",
      justifyContent: "center",
    },
  });
}
