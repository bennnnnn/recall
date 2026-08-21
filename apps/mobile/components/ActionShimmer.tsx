import { lazy, Suspense, useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import type { ActionShimmerProps } from "@/components/ActionShimmerMotion";

const LazyActionShimmerMotion = lazy(() => import("@/components/ActionShimmerMotion"));

/**
 * Indeterminate action progress. The label remains readable immediately; the
 * sweep starts after a short delay so fast actions do not flash animation.
 */
export function ActionShimmer(props: ActionShimmerProps) {
  const { label, color, compact = false, style, textStyle, testID } = props;
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const ink = color ?? theme.primary;

  return (
    <Suspense
      fallback={
        <View
          testID={testID}
          style={[s.wrap, compact && s.compact, style]}
          accessibilityRole="progressbar"
          accessibilityLabel={label}
          accessibilityLiveRegion="polite"
        >
          <View style={[s.dot, { backgroundColor: ink }]} />
          <Text style={[s.label, { color: ink }, textStyle]} numberOfLines={1}>
            {label}
          </Text>
        </View>
      }
    >
      <LazyActionShimmerMotion {...props} />
    </Suspense>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: {
      minHeight: 24,
      minWidth: 72,
      alignSelf: "center",
      alignItems: "center",
      justifyContent: "center",
      flexDirection: "row",
      gap: Space.xs,
      overflow: "hidden",
      borderRadius: Radius.sm,
      paddingHorizontal: Space.xs,
    },
    compact: {
      minHeight: 18,
      minWidth: 0,
      paddingHorizontal: 0,
    },
    label: {
      color: theme.primary,
      fontSize: 14,
      fontWeight: "700",
    },
    dot: {
      width: 6,
      height: 6,
      borderRadius: Radius.full,
    },
  });
}
