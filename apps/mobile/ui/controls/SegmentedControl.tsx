import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from "react-native-reanimated";

import { selection } from "@/lib/haptics";
import { Motion, useReduceMotion } from "@/lib/motion";
import { shadowRaised } from "@/lib/shadow";
import { Space } from "@/lib/space";
import { type Theme, useTheme, withAlpha } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

type Segment<K extends string> = { key: K; label: string };

type Props<K extends string> = {
  segments: readonly Segment<K>[];
  value: K;
  onChange: (key: K) => void;
  /** Spoken name of the choice, e.g. "Text size". */
  accessibilityLabel?: string;
  /** On a tinted background: a see-through track that takes the tint, not a grey one. */
  tinted?: boolean;
  testID?: string;
};

/**
 * Pick one of two to four short options in place (Small · Medium · Large).
 * A raised thumb slides to the choice. For longer lists use SelectMenu.
 */
export function SegmentedControl<K extends string>({
  segments,
  value,
  onChange,
  accessibilityLabel,
  tinted = false,
  testID = "segmented",
}: Props<K>) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const reduceMotion = useReduceMotion();
  const [width, setWidth] = useState(0);
  const index = Math.max(
    0,
    segments.findIndex((segment) => segment.key === value),
  );
  const segmentWidth = width > 0 ? (width - Space.xxs * 2) / segments.length : 0;
  const offset = useSharedValue(index * segmentWidth);

  useEffect(() => {
    const target = index * segmentWidth;
    offset.value =
      reduceMotion || segmentWidth === 0 ? target : withSpring(target, Motion.spring.press);
  }, [index, segmentWidth, reduceMotion, offset]);

  const thumbStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: offset.value }],
  }));

  return (
    <View
      style={[s.track, tinted && s.trackTinted]}
      onLayout={(event) => setWidth(event.nativeEvent.layout.width)}
      accessibilityRole="radiogroup"
      accessibilityLabel={accessibilityLabel}
      testID={testID}
    >
      {segmentWidth > 0 ? (
        <Animated.View
          pointerEvents="none"
          style={[s.thumb, { width: segmentWidth }, thumbStyle]}
          testID={`${testID}-thumb`}
        />
      ) : null}
      {segments.map((segment) => {
        const selected = segment.key === value;
        return (
          <Pressable
            key={segment.key}
            style={s.segment}
            // 40pt segment in a 4pt-padded track: the track's edge is the 44pt target's.
            hitSlop={{ top: 2, bottom: 2 }}
            onPress={() => {
              if (selected) return;
              selection();
              onChange(segment.key);
            }}
            accessibilityRole="radio"
            accessibilityState={{ checked: selected }}
            accessibilityLabel={segment.label}
            testID={`${testID}-${segment.key}`}
          >
            {/* A label wraps, never cuts: "Yearly · Save 37%" at the largest text size. */}
            <Text style={[s.label, selected && s.labelOn]}>{segment.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/** A one-line segment's height; its corners are half of it, a pill that stays a pill's
 * shape (a rounded box, not an oval) when a label wraps to more lines. */
const SEGMENT_HEIGHT = Space.xl + Space.xs;
const SEGMENT_RADIUS = SEGMENT_HEIGHT / 2;

function makeStyles(t: Theme) {
  return StyleSheet.create({
    // The thumb is always the lighter of the two, so the choice reads as raised.
    track: {
      flexDirection: "row",
      padding: Space.xxs,
      borderRadius: SEGMENT_RADIUS + Space.xxs,
      backgroundColor: t.isDark ? t.surface : t.control,
    },
    trackTinted: { backgroundColor: withAlpha(t.isDark ? t.surface : t.elevated, 0.55) },
    thumb: {
      position: "absolute",
      top: Space.xxs,
      bottom: Space.xxs,
      left: Space.xxs,
      borderRadius: SEGMENT_RADIUS,
      backgroundColor: t.isDark ? t.control : t.elevated,
      ...shadowRaised(t),
    },
    segment: {
      flex: 1,
      minHeight: SEGMENT_HEIGHT,
      paddingHorizontal: Space.xs,
      paddingVertical: Space.xxs,
      borderRadius: SEGMENT_RADIUS,
      alignItems: "center",
      justifyContent: "center",
    },
    label: { ...Type.label, ...Weight.medium, color: t.textSecondary, textAlign: "center" },
    labelOn: { ...Weight.semibold, color: t.text },
  });
}
