import { useEffect, useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from "react-native-reanimated";

import { Theme, useTheme } from "@/lib/theme";

/** Pulsing Recall mark while waiting for the first token (ChatGPT-style). */
export function RecallTypingIndicator() {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const scale = useSharedValue(0.92);
  const opacity = useSharedValue(0.45);
  const glow = useSharedValue(0.3);

  useEffect(() => {
    const ease = Easing.inOut(Easing.ease);
    scale.value = withRepeat(
      withSequence(
        withTiming(1.06, { duration: 700, easing: ease }),
        withTiming(0.92, { duration: 700, easing: ease }),
      ),
      -1,
      false,
    );
    opacity.value = withRepeat(
      withSequence(
        withTiming(1, { duration: 700, easing: ease }),
        withTiming(0.5, { duration: 700, easing: ease }),
      ),
      -1,
      false,
    );
    glow.value = withRepeat(
      withSequence(
        withTiming(0.55, { duration: 700, easing: ease }),
        withTiming(0.2, { duration: 700, easing: ease }),
      ),
      -1,
      false,
    );
  }, [glow, opacity, scale]);

  const logoStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
    opacity: opacity.value,
  }));

  const haloStyle = useAnimatedStyle(() => ({
    opacity: glow.value,
    transform: [{ scale: scale.value * 1.35 }],
  }));

  return (
    <View style={s.wrap}>
      <Animated.View style={[s.halo, haloStyle]} />
      <Animated.View style={[s.logo, logoStyle]}>
        <Text style={s.letter}>R</Text>
      </Animated.View>
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: {
      width: 36,
      height: 36,
      alignItems: "center",
      justifyContent: "center",
      paddingVertical: 4,
    },
    halo: {
      position: "absolute",
      width: 28,
      height: 28,
      borderRadius: 14,
      backgroundColor: t.primary,
    },
    logo: {
      width: 28,
      height: 28,
      borderRadius: 14,
      backgroundColor: t.primary,
      alignItems: "center",
      justifyContent: "center",
    },
    letter: {
      color: "#fff",
      fontSize: 15,
      fontWeight: "700",
      marginTop: -1,
    },
  });
}
