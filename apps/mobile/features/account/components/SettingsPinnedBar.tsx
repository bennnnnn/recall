import { useEffect, useState } from "react";
import { Animated, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { HEADER_BUTTON_SIZE } from "@/ui/controls/HeaderButton";
import { StackBackButton } from "@/ui/controls/StackBackButton";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

/** How far the page scrolls before the bar is fully drawn. */
const FADE_DISTANCE = Space.xl;

/**
 * The bar of a Settings page without a stack header (Settings home). Back stays on screen
 * while the page scrolls (it used to scroll away with the profile); the bar's background
 * and title fade in as rows pass under it, so at rest the page looks as if it had no bar.
 */
export function SettingsPinnedBar({ title, scrollY }: { title: string; scrollY: Animated.Value }) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const shown = scrollY.interpolate({
    inputRange: [0, FADE_DISTANCE],
    outputRange: [0, 1],
    extrapolate: "clamp",
  });
  // Drawn, the bar keeps a tap on it from pressing the row hidden under it; unseen at rest,
  // it lets every tap through to the profile.
  const [covering, setCovering] = useState(false);
  useEffect(() => {
    const id = scrollY.addListener(({ value }) => setCovering(value > FADE_DISTANCE / 2));
    return () => scrollY.removeListener(id);
  }, [scrollY]);
  return (
    <View
      pointerEvents="box-none"
      style={[s.bar, { paddingTop: insets.top + Space.md }]}
      testID="settings-pinned-bar"
    >
      <Animated.View
        pointerEvents={covering ? "auto" : "none"}
        testID="settings-pinned-bar-backdrop"
        style={[
          StyleSheet.absoluteFill,
          { backgroundColor: theme.bg, borderBottomColor: theme.separator, opacity: shown },
          s.backdrop,
        ]}
      />
      <StackBackButton />
      <Animated.Text
        pointerEvents="none"
        style={[s.title, { color: theme.text, opacity: shown }]}
        numberOfLines={1}
        importantForAccessibility="no"
        accessibilityElementsHidden
      >
        {title}
      </Animated.Text>
    </View>
  );
}

const s = StyleSheet.create({
  bar: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: Space.md,
    paddingBottom: Space.xs,
  },
  backdrop: { borderBottomWidth: StyleSheet.hairlineWidth },
  // Centred on the page, clear of Back on either side.
  title: {
    ...Type.navTitle,
    position: "absolute",
    left: HEADER_BUTTON_SIZE + Space.md * 2,
    right: HEADER_BUTTON_SIZE + Space.md * 2,
    bottom: Space.xs + (HEADER_BUTTON_SIZE - Type.navTitle.lineHeight) / 2,
    textAlign: "center",
  },
});
