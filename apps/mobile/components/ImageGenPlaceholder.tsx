import { useEffect, useMemo } from "react";
import { StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from "react-native-reanimated";

import { useThumbnailSize } from "@/components/ChatMessageImage";
import { Motion } from "@/lib/motion";
import { Theme, useTheme } from "@/lib/theme";

/** Pulsing placeholder shown while an image is being generated — the
 * "background" stage of the background > blur > image reveal. Sized to
 * match ChatMessageImage's thumbnail exactly so there's no layout jump
 * when the real image swaps in. */
export function ImageGenPlaceholder() {
  const C = useTheme();
  const { width, height } = useThumbnailSize();
  const s = useMemo(() => makeStyles(C, width, height), [C, width, height]);
  const opacity = useSharedValue(0.55);

  useEffect(() => {
    opacity.value = withRepeat(
      withSequence(
        withTiming(1, {
          duration: Motion.duration.soft,
          easing: Motion.easing.inOut,
        }),
        withTiming(0.55, {
          duration: Motion.duration.soft,
          easing: Motion.easing.inOut,
        }),
      ),
      -1,
      false,
    );
  }, [opacity]);

  const animatedStyle = useAnimatedStyle(() => ({ opacity: opacity.value }));

  return (
    <View style={s.wrap}>
      <Animated.View style={[s.fill, animatedStyle]}>
        <Ionicons name="image-outline" size={28} color={C.textTertiary} />
      </Animated.View>
    </View>
  );
}

function makeStyles(C: Theme, width: number, height: number) {
  return StyleSheet.create({
    wrap: {
      width,
      height,
      borderRadius: 22,
      overflow: "hidden",
      backgroundColor: C.surfaceAlt,
    },
    fill: {
      width: "100%",
      height: "100%",
      alignItems: "center",
      justifyContent: "center",
    },
  });
}
