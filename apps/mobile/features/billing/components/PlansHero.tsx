/**
 * The plans page's picture: a student reading at a desk by a night window, in the brand's
 * indigo (`assets/images/plans-art.jpg`, made for this page). It keeps its shape on every
 * phone and is cropped, not squeezed, when a small screen needs the room.
 */
import { useMemo } from "react";
import { Image, StyleSheet, View } from "react-native";

import { Radius } from "@/lib/radius";
import { Theme, useTheme } from "@/lib/theme";

const ART = require("@/assets/images/plans-art.jpg") as number;

/** The picture's height for a screen of `height`: smaller on a small phone, never cramped. */
export function heroHeight(height: number): number {
  return Math.min(190, Math.max(96, height - 730));
}

export function PlansHero({ height }: { height: number }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <View style={[s.frame, { height }]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Image source={ART} style={s.art} resizeMode="cover" />
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    frame: { borderRadius: Radius.xl, overflow: "hidden", backgroundColor: theme.surface },
    art: { width: "100%", height: "100%" },
  });
}
