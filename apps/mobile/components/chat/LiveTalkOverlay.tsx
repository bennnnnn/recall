import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { LiveTalkOrb } from "@/components/chat/LiveTalkOrb";
import {
  liveTalkCanTakeFloor,
  liveTalkHintKey,
  liveTalkOrbA11yKey,
  liveTalkOrbAction,
  liveTalkSpeakerA11yKey,
  liveTalkSpeakerAction,
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
  /** Leave this strip open so ChatHeader (hamburger / ⋮) stays tappable. */
  headerInset: number;
  onClose: () => void;
  onToggle: () => void;
  onSpeakerPress: () => void;
  onInterrupt: () => void;
};

export function LiveTalkOverlay({
  visible,
  phase,
  meterLevel,
  recording,
  headerInset,
  onClose,
  onToggle,
  onSpeakerPress,
  onInterrupt,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const takeFloor = liveTalkCanTakeFloor(phase);
  const hint = t(liveTalkHintKey(phase));
  const orbAction = liveTalkOrbAction(phase);
  const speakerAction = liveTalkSpeakerAction(phase);
  const speakerA11y = liveTalkSpeakerA11yKey(phase);

  if (!visible) return null;

  const orb = (
    <LiveTalkOrb
      theme={theme}
      phase={phase === "paused" ? "idle" : phase}
      meterLevel={meterLevel}
      recording={recording}
      reduceMotion={reduceMotion}
    />
  );

  return (
    <View style={[s.overlay, { top: headerInset }]} testID="live-talk-overlay">
      <View style={[s.body, { paddingBottom: insets.bottom + 16 }]}>
        <View style={s.center}>
          {orbAction === "none" ? (
            <View testID="live-talk-orb">{orb}</View>
          ) : (
            <Pressable
              onPress={onToggle}
              accessibilityRole="button"
              accessibilityLabel={t(liveTalkOrbA11yKey(phase))}
              testID="live-talk-orb"
            >
              {orb}
            </Pressable>
          )}
          <Text style={s.hint}>{hint}</Text>
          {speakerAction && speakerA11y ? (
            <Pressable
              onPress={onSpeakerPress}
              style={[s.speakerBtn, { borderColor: theme.composerBorder, backgroundColor: theme.inputBg }]}
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
          ) : null}
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
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    overlay: {
      position: "absolute",
      left: 0,
      right: 0,
      bottom: 0,
      zIndex: 120,
    },
    body: {
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
    speakerBtn: {
      width: 52,
      height: 52,
      borderRadius: 26,
      borderWidth: StyleSheet.hairlineWidth,
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
