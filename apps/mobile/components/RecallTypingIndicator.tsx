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

/** Pulsing Recall mark while waiting for the first token (ChatGPT-style).
 * The logo scales/fades and rotates back and forth (pendulum, not a full spin)
 * so the "thinking" state reads as active processing. */
export function RecallTypingIndicator() {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const scale = useSharedValue(0.92);
  const opacity = useSharedValue(0.45);
  const rotate = useSharedValue(0);

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
    // Pendulum: swing -22° → +22° → -22°, ease-in-out so it eases at the
    // extremes (looks like it's "thinking back and forth", not a uniform spin).
    rotate.value = withRepeat(
      withSequence(
        withTiming(22, { duration: 650, easing: Easing.inOut(Easing.sin) }),
        withTiming(-22, { duration: 650, easing: Easing.inOut(Easing.sin) }),
      ),
      -1,
      false,
    );
  }, [opacity, rotate, scale]);

  const logoStyle = useAnimatedStyle(() => ({
    transform: [{ rotate: `${rotate.value}deg` }, { scale: scale.value }],
    opacity: opacity.value,
  }));

  return (
    <View style={s.wrap}>
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
    logo: {
      width: 28,
      height: 28,
      borderRadius: 14,
      backgroundColor: t.primary,
      alignItems: "center",
      justifyContent: "center",
    },
    letter: {
      color: t.onPrimary,
      fontSize: 15,
      fontWeight: "700",
      marginTop: -1,
    },
  });
}
