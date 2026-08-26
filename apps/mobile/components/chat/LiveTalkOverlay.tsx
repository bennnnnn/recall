import { useMemo } from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { LiveTalkOrb } from "@/components/chat/LiveTalkOrb";
import { type LiveTalkPhase } from "@/lib/liveTalkLogic";
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
};

export function LiveTalkOverlay({
  visible,
  phase,
  meterLevel,
  recording,
  onClose,
  onToggle,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const busy = phase === "thinking";

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
            onPress={() => {
              if (!busy) onToggle();
            }}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel={t("chat.live_talk_a11y")}
            testID="live-talk-orb"
          >
            <LiveTalkOrb
              theme={theme}
              phase={phase}
              meterLevel={meterLevel}
              recording={recording}
              reduceMotion={reduceMotion}
            />
          </Pressable>
        </View>

        <View style={s.bottom}>
          <View
            style={[s.pill, { backgroundColor: theme.inputBg, borderColor: theme.composerBorder }]}
          >
            <Icon name="add-outline" size={22} color={theme.text} />
            <Text style={s.pillText}>{t("chat.live_talk_ask")}</Text>
          </View>
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
    pillText: {
      ...Type.body,
      color: theme.textTertiary,
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
