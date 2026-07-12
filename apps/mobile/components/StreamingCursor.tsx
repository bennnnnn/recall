import { useEffect, useMemo } from "react";
import { StyleSheet, View } from "react-native";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from "react-native-reanimated";

import { Theme, useTheme } from "@/lib/theme";

/** Blinking caret shown while assistant text is streaming in. */
export function StreamingCursor() {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const opacity = useSharedValue(1);

  useEffect(() => {
    const ease = Easing.inOut(Easing.ease);
    opacity.value = withRepeat(
      withSequence(
        withTiming(0.15, { duration: 450, easing: ease }),
        withTiming(1, { duration: 450, easing: ease }),
      ),
      -1,
      false,
    );
  }, [opacity]);

  const caretStyle = useAnimatedStyle(() => ({
    opacity: opacity.value,
  }));

  return (
    <View style={s.wrap} accessibilityElementsHidden importantForAccessibility="no">
      <Animated.View style={[s.caret, caretStyle]} />
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: {
      alignSelf: "flex-start",
      marginTop: -2,
      marginBottom: 4,
      paddingLeft: 1,
    },
    caret: {
      width: 2,
      height: 18,
      borderRadius: 1,
      backgroundColor: t.accent,
    },
  });
}
