/* eslint-disable react-hooks/immutability -- Reanimated shared values mutate `.value` in gestures. */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  View,
  type AccessibilityActionEvent,
  type LayoutChangeEvent,
} from "react-native";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import Animated, { runOnJS, useAnimatedStyle, useSharedValue } from "react-native-reanimated";

import { Radius } from "@/lib/radius";
import { shadowRaised } from "@/lib/shadow";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { sliderFraction, sliderValueAt, steppedSliderValue } from "@/ui/controls/sliderValue";

const THUMB = 24;
const TRACK = 4;
const TICK = 12;

/** A reference value on the track, such as today's average rate. Tapping it jumps there. */
type SliderMarker = {
  value: number;
  /** The short label under the tick ("Avg 6.27% · Oct 16"). */
  label: string;
  /** Spoken for the tick; the label is used when omitted. */
  accessibilityLabel?: string;
};

type Props = {
  /** The quantity's name, shown above the track and spoken. */
  label: string;
  /** The value as the reader should see and hear it ("$300,000", "6.27%"). */
  valueText: string;
  value: number;
  min: number;
  max: number;
  step: number;
  /** Every new value while the finger moves (already on the step grid). */
  onChange: (value: number) => void;
  marker?: SliderMarker | null;
  testID?: string;
};

/**
 * Pick a number in a range by dragging (an amount, a rate, a term). The label and the
 * value sit above the track; an optional marker shows a reference value under it. Drag
 * or tap the track; a screen reader steps it with the adjustable actions.
 */
export function Slider({
  label,
  valueText,
  value,
  min,
  max,
  step,
  onChange,
  marker,
  testID = "slider",
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [width, setWidth] = useState(0);
  const [markerWidth, setMarkerWidth] = useState(0);
  const usable = Math.max(0, width - THUMB);
  const at = sliderFraction(value, min, max);
  // Where the finger is while it drags, or -1: the thumb then sits at the value.
  const finger = useSharedValue(-1);
  const usableWidth = useSharedValue(usable);
  const dragging = useRef(false);
  // The gesture is built once; its callbacks read the newest props from here.
  const latest = useRef({ value, min, max, step, onChange });
  useEffect(() => {
    latest.current = { value, min, max, step, onChange };
  });

  useEffect(() => {
    usableWidth.value = usable;
  }, [usable, usableWidth]);

  const moveTo = useCallback((fraction: number) => {
    const current = latest.current;
    dragging.current = true;
    const next = sliderValueAt(fraction, current.min, current.max, current.step);
    if (next !== current.value) current.onChange(next);
  }, []);

  const release = useCallback(() => {
    dragging.current = false;
    finger.value = -1;
  }, [finger]);

  // A drag that ends, or one the list's scroll takes over, lets go once.
  const finish = useCallback(() => {
    if (dragging.current) release();
  }, [release]);

  const jump = useCallback((next: number) => {
    const current = latest.current;
    if (next !== current.value) current.onChange(next);
  }, []);

  /* eslint-disable react-hooks/refs -- the gesture callbacks read refs on touch, not in render */
  const gesture = useMemo(() => {
    const pan = Gesture.Pan()
      .activeOffsetX([-4, 4])
      .failOffsetY([-12, 12])
      .onUpdate((event) => {
        const room = usableWidth.value;
        if (room <= 0) return;
        const fraction = Math.min(1, Math.max(0, (event.x - THUMB / 2) / room));
        finger.value = fraction;
        runOnJS(moveTo)(fraction);
      })
      .onFinalize(() => {
        runOnJS(finish)();
      });
    const tap = Gesture.Tap()
      .onEnd((event) => {
        const room = usableWidth.value;
        if (room <= 0) return;
        const fraction = Math.min(1, Math.max(0, (event.x - THUMB / 2) / room));
        runOnJS(moveTo)(fraction);
        runOnJS(release)();
      });
    return Gesture.Exclusive(pan, tap);
  }, [finger, finish, moveTo, release, usableWidth]);
  /* eslint-enable react-hooks/refs */

  const thumbStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: (finger.value >= 0 ? finger.value : at) * usableWidth.value }],
  }));
  const fillStyle = useAnimatedStyle(() => ({
    width: (finger.value >= 0 ? finger.value : at) * usableWidth.value + THUMB / 2,
  }));

  const onA11yAction = (event: AccessibilityActionEvent) => {
    const name = event.nativeEvent.actionName;
    if (name !== "increment" && name !== "decrement") return;
    jump(steppedSliderValue(value, name === "increment" ? 1 : -1, min, max, step));
  };

  const markerAt = marker ? sliderFraction(marker.value, min, max) * usable + THUMB / 2 : 0;
  const markerLeft = Math.min(Math.max(0, markerAt - markerWidth / 2), Math.max(0, width - markerWidth));

  return (
    <View style={s.root} testID={testID}>
      <View style={s.header}>
        <Text style={s.label} numberOfLines={1}>
          {label}
        </Text>
        <Text style={s.value} numberOfLines={1} testID={`${testID}-value`}>
          {valueText}
        </Text>
      </View>
      <GestureDetector gesture={gesture}>
        <View
          style={s.hit}
          onLayout={(event: LayoutChangeEvent) => setWidth(event.nativeEvent.layout.width)}
          accessible
          accessibilityRole="adjustable"
          accessibilityLabel={label}
          accessibilityValue={{ min, max, now: value, text: valueText }}
          accessibilityActions={[{ name: "increment" }, { name: "decrement" }]}
          onAccessibilityAction={onA11yAction}
          testID={`${testID}-track`}
        >
          <View style={s.track} />
          <Animated.View style={[s.fill, fillStyle]} />
          {marker ? (
            <View pointerEvents="none" style={[s.tick, { left: markerAt - StyleSheet.hairlineWidth }]} />
          ) : null}
          <Animated.View pointerEvents="none" style={[s.thumb, thumbStyle]} />
        </View>
      </GestureDetector>
      {marker ? (
        <View style={s.markerRow}>
          <Pressable
            onPress={() => jump(Math.min(max, Math.max(min, marker.value)))}
            onLayout={(event: LayoutChangeEvent) => setMarkerWidth(event.nativeEvent.layout.width)}
            hitSlop={8}
            style={({ pressed }) => [s.marker, { left: markerLeft }, pressed && s.pressed]}
            accessibilityRole="button"
            accessibilityLabel={marker.accessibilityLabel ?? marker.label}
            testID={`${testID}-marker`}
          >
            <Text style={s.markerText} numberOfLines={1}>
              {marker.label}
            </Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    root: { gap: Space.xxs },
    header: { flexDirection: "row", alignItems: "baseline", gap: Space.xs },
    label: { flex: 1, ...Type.secondary, color: t.textSecondary },
    value: { ...Type.label, ...Weight.semibold, color: t.text, fontVariant: ["tabular-nums"] },
    hit: { height: THUMB + Space.xs * 2, justifyContent: "center" },
    track: {
      position: "absolute",
      left: THUMB / 2,
      right: THUMB / 2,
      height: TRACK,
      borderRadius: Radius.full,
      backgroundColor: t.surfaceAlt,
    },
    fill: {
      position: "absolute",
      left: 0,
      height: TRACK,
      borderRadius: Radius.full,
      backgroundColor: t.primary,
    },
    tick: {
      position: "absolute",
      width: StyleSheet.hairlineWidth * 2,
      height: TICK,
      backgroundColor: t.textSecondary,
    },
    thumb: {
      position: "absolute",
      left: 0,
      width: THUMB,
      height: THUMB,
      borderRadius: Radius.full,
      backgroundColor: t.elevated,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      ...shadowRaised(t),
    },
    markerRow: { minHeight: Space.md },
    marker: { position: "absolute", top: 0 },
    markerText: { ...Type.caption, color: t.textSecondary },
    pressed: { opacity: 0.6 },
  });
}
