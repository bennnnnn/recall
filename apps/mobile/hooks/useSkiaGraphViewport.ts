import { useEffect } from "react";
import { Gesture } from "react-native-gesture-handler";
import { runOnJS, useSharedValue } from "react-native-reanimated";

import {
  clampGraphViewW,
  panGraphViewW,
  unmapPointW,
  zoomGraphViewW,
  type GraphViewW,
} from "@/lib/math/graphWorklets";
import type { GraphView } from "@/lib/math/graphViewport";

type Args = {
  width: number;
  height: number;
  pad: number;
  initialView: GraphView;
  /** Called once per gesture end so the JS side can resample for the new window. */
  onCommit: (bounds: GraphView) => void;
  /** Fired when trace mode turns on/off or the snapped sample changes. */
  onTraceTick?: () => void;
};

/**
 * UI-thread viewport for the Skia explorer: bounds live in a shared value and
 * gestures mutate them in worklets, so pan/zoom never round-trips through
 * React state. JS is notified once per gesture end (onCommit) to resample.
 */
export function useSkiaGraphViewport({
  width,
  height,
  pad,
  initialView,
  onCommit,
  onTraceTick,
}: Args) {
  const bounds = useSharedValue<GraphViewW>(initialView);
  const gestureStart = useSharedValue<GraphViewW>(initialView);
  const traceActive = useSharedValue(false);
  /** Finger position in pixels while tracing. */
  const tracePos = useSharedValue({ px: 0, py: 0 });

  useEffect(() => {
    bounds.value = initialView;
    gestureStart.value = initialView;
    // Shared values are mutable refs — only reseed for a genuinely new window.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialView]);

  const commit = (next: GraphViewW) => {
    "worklet";
    runOnJS(onCommit)(next);
  };
  const traceTick = () => {
    "worklet";
    if (onTraceTick) runOnJS(onTraceTick)();
  };

  const pinch = Gesture.Pinch()
    .onBegin(() => {
      "worklet";
      gestureStart.value = bounds.value;
    })
    .onUpdate((e) => {
      "worklet";
      const focal = unmapPointW(e.focalX, e.focalY, gestureStart.value, width, height, pad);
      bounds.value = zoomGraphViewW(gestureStart.value, e.scale, focal.x, focal.y);
    })
    .onEnd(() => {
      "worklet";
      commit(bounds.value);
    });

  const longPress = Gesture.LongPress()
    .minDuration(220)
    .onStart((e) => {
      "worklet";
      traceActive.value = true;
      tracePos.value = { px: e.x, py: e.y };
      traceTick();
    });

  const pan = Gesture.Pan()
    .minDistance(10)
    .maxPointers(1)
    .onBegin(() => {
      "worklet";
      gestureStart.value = bounds.value;
    })
    .onUpdate((e) => {
      "worklet";
      if (traceActive.value) {
        tracePos.value = { px: e.x, py: e.y };
        return;
      }
      bounds.value = panGraphViewW(
        gestureStart.value,
        e.translationX,
        e.translationY,
        width,
        height,
        pad,
      );
    })
    .onEnd(() => {
      "worklet";
      if (traceActive.value) {
        traceActive.value = false;
        return;
      }
      commit(bounds.value);
    })
    .onFinalize(() => {
      "worklet";
      traceActive.value = false;
    });

  const doubleTap = Gesture.Tap()
    .numberOfTaps(2)
    .onEnd(() => {
      "worklet";
      bounds.value = clampGraphViewW(initialView);
      commit(bounds.value);
    });

  const gesture = Gesture.Simultaneous(pinch, pan, doubleTap, longPress);

  return { bounds, gesture, traceActive, tracePos };
}
