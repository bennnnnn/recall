import { useMemo } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { useTranslation } from "react-i18next";

import { LiveTalkOrb } from "@/components/chat/LiveTalkOrb";
import { liveTalkOrbA11yKey, liveTalkOrbAction, type LiveTalkPhase } from "@/lib/liveTalkLogic";
import { useReduceMotion } from "@/lib/motion";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  visible: boolean;
  phase: LiveTalkPhase;
  meterLevel: number;
  recording: boolean;
  /** Leave this strip open so ChatHeader (hamburger / ⋮) stays tappable. */
  headerInset: number;
  /** Leave the real composer (type / attach) uncovered. */
  composerClearance: number;
  onToggle: () => void;
};

export function LiveTalkOverlay({
  visible,
  phase,
  meterLevel,
  recording,
  headerInset,
  composerClearance,
  onToggle,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const reduceMotion = useReduceMotion();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const orbAction = liveTalkOrbAction(phase);

  if (!visible) return null;

  const orb = (
    <LiveTalkOrb
      theme={theme}
      phase={phase}
      meterLevel={meterLevel}
      recording={recording}
      reduceMotion={reduceMotion}
    />
  );

  return (
    <View
      style={[s.overlay, { top: headerInset, bottom: composerClearance }]}
      testID="live-talk-overlay"
    >
      <View style={s.body}>
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
      zIndex: 120,
    },
    body: {
      flex: 1,
      backgroundColor: theme.bg,
      alignItems: "center",
      justifyContent: "center",
    },
  });
}
