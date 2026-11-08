/* eslint-disable react-hooks/immutability -- Reanimated shared values mutate `.value` in gestures. */
import { useCallback, useEffect, useMemo, useRef } from "react";
import { Gesture } from "react-native-gesture-handler";
import {
  runOnJS,
  runOnUI,
  useAnimatedReaction,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";

import { Motion, motionMs } from "@/lib/motion";
import {
  type ScanChromeInset,
  type ScanCorner,
  type ScanRegion,
  clampScanRegion,
  defaultScanRegion,
  DEFAULT_REGION_HEIGHT,
  DEFAULT_REGION_WIDTH,
  resizeScanRegionFromCorner,
  scaleScanRegion,
  translateScanRegion,
  zoomFromPinch,
} from "@/lib/math/scannerRegion";
import { useCornerHandleStyles } from "@/features/scanner/hooks/useCornerHandleStyles";

const ZOOM_PUSH_DELTA = 0.02;
/** theme.scrim is ~0.40 idle; multiply by this while dragging → ~0.25. */
const MASK_DRAG_OPACITY = 0.625;

type Point = { x: number; y: number };

type Args = {
  windowWidth: number;
  windowHeight: number;
  inset: ScanChromeInset;
  preview: boolean;
  reduceMotion: boolean;
  onZoom: (zoom: number) => void;
  onRegionChange?: (region: ScanRegion) => void;
  /** A tap inside the frame, in view points (the camera focuses there). */
  onTap?: (point: Point) => void;
};

export function useMathScannerCrop({
  windowWidth,
  windowHeight,
  inset,
  preview,
  reduceMotion,
  onZoom,
  onRegionChange,
  onTap,
}: Args) {
  const region = useSharedValue<ScanRegion>(defaultScanRegion(inset));
  const dragging = useSharedValue(0);
  const previewSv = useSharedValue(preview);
  const zoomSv = useSharedValue(0);
  const lastPushedZoom = useSharedValue(0);
  const insetSv = useSharedValue(inset);
  const pinchStartZoom = useSharedValue(0);
  const pinchStartRegion = useSharedValue<ScanRegion>(defaultScanRegion(inset));
  const panBase = useSharedValue<ScanRegion>(defaultScanRegion(inset));
  const panOriginX = useSharedValue(0);
  const panOriginY = useSharedValue(0);
  const cornerBase = useSharedValue<ScanRegion>(defaultScanRegion(inset));

  useEffect(() => {
    insetSv.value = inset;
    const next = clampScanRegion(region.value, inset);
    region.value = next;
    onRegionChange?.(next);
  }, [inset, insetSv, onRegionChange, region]);

  useEffect(() => {
    previewSv.value = preview;
  }, [preview, previewSv]);

  const dragDuration = motionMs(Motion.duration.standard, reduceMotion);
  const pushRegion = useCallback(
    (next: ScanRegion) => onRegionChange?.(next),
    [onRegionChange],
  );
  // Times the student moved or resized the frame; a frame fit compares it (`useScanContentFit`).
  const adjustCount = useRef(0);
  const adjust = useCallback(() => {
    adjustCount.current += 1;
  }, []);
  const tap = useCallback((point: Point) => onTap?.(point), [onTap]);

  useAnimatedReaction(
    () => zoomSv.value,
    (current) => {
      if (Math.abs(current - lastPushedZoom.value) < ZOOM_PUSH_DELTA) return;
      lastPushedZoom.value = current;
      runOnJS(onZoom)(current);
    },
    [onZoom],
  );

  const pinchGesture = useMemo(
    () =>
      Gesture.Pinch()
        .onBegin(() => {
          pinchStartZoom.value = zoomSv.value;
          pinchStartRegion.value = region.value;
          dragging.value = 1;
        })
        .onStart(() => {
          if (previewSv.value) runOnJS(adjust)();
        })
        .onUpdate((e) => {
          if (previewSv.value) {
            region.value = scaleScanRegion(pinchStartRegion.value, e.scale, insetSv.value);
            return;
          }
          zoomSv.value = zoomFromPinch(pinchStartZoom.value, e.scale);
        })
        .onEnd(() => {
          if (previewSv.value) runOnJS(pushRegion)(region.value);
          else runOnJS(onZoom)(zoomSv.value);
        })
        // A touch that never became a pinch (a tap) ends here too, not in onEnd.
        .onFinalize(() => {
          dragging.value = withTiming(0, { duration: dragDuration });
        }),
    [
      adjust,
      dragDuration,
      dragging,
      insetSv,
      onZoom,
      pinchStartRegion,
      pinchStartZoom,
      previewSv,
      pushRegion,
      region,
      zoomSv,
    ],
  );

  const panGesture = useMemo(
    () =>
      Gesture.Pan()
        .maxPointers(1)
        .onBegin(() => {
          dragging.value = 1;
        })
        .onStart((e) => {
          panBase.value = region.value;
          panOriginX.value = e.translationX;
          panOriginY.value = e.translationY;
          runOnJS(adjust)();
        })
        .onUpdate((e) => {
          const dx = (e.translationX - panOriginX.value) / windowWidth;
          const dy = (e.translationY - panOriginY.value) / windowHeight;
          region.value = translateScanRegion(panBase.value, dx, dy, insetSv.value);
        })
        .onEnd(() => {
          runOnJS(pushRegion)(region.value);
        })
        .onFinalize(() => {
          dragging.value = withTiming(0, { duration: dragDuration });
        }),
    [
      adjust,
      dragDuration,
      dragging,
      insetSv,
      panBase,
      panOriginX,
      panOriginY,
      pushRegion,
      region,
      windowHeight,
      windowWidth,
    ],
  );

  const makeCornerGesture = useCallback(
    (corner: ScanCorner) =>
      Gesture.Pan()
        .maxPointers(1)
        .onBegin(() => {
          dragging.value = 1;
        })
        .onStart((e) => {
          cornerBase.value = region.value;
          panOriginX.value = e.translationX;
          panOriginY.value = e.translationY;
          runOnJS(adjust)();
        })
        .onUpdate((e) => {
          const dx = (e.translationX - panOriginX.value) / windowWidth;
          const dy = (e.translationY - panOriginY.value) / windowHeight;
          region.value = resizeScanRegionFromCorner(cornerBase.value, corner, dx, dy, insetSv.value);
        })
        .onEnd(() => {
          runOnJS(pushRegion)(region.value);
        })
        .onFinalize(() => {
          dragging.value = withTiming(0, { duration: dragDuration });
        }),
    [
      adjust,
      cornerBase,
      dragDuration,
      dragging,
      insetSv,
      panOriginX,
      panOriginY,
      pushRegion,
      region,
      windowHeight,
      windowWidth,
    ],
  );

  const cornerTL = useMemo(() => makeCornerGesture("tl"), [makeCornerGesture]);
  const cornerTR = useMemo(() => makeCornerGesture("tr"), [makeCornerGesture]);
  const cornerBL = useMemo(() => makeCornerGesture("bl"), [makeCornerGesture]);
  const cornerBR = useMemo(() => makeCornerGesture("br"), [makeCornerGesture]);

  const tapGesture = useMemo(
    () =>
      Gesture.Tap().onEnd((e) => {
        const r = region.value;
        runOnJS(tap)({ x: r.x * windowWidth + e.x, y: r.y * windowHeight + e.y });
      }),
    [region, tap, windowHeight, windowWidth],
  );

  const regionGesture = useMemo(
    () => Gesture.Simultaneous(pinchGesture, panGesture, tapGesture),
    [pinchGesture, panGesture, tapGesture],
  );

  const regionStyle = useAnimatedStyle(() => {
    const r = region.value;
    return {
      left: r.x * windowWidth,
      top: r.y * windowHeight,
      width: r.width * windowWidth,
      height: r.height * windowHeight,
    };
  });

  const maskTopStyle = useAnimatedStyle(() => ({
    height: region.value.y * windowHeight,
    opacity: 1 - dragging.value * (1 - MASK_DRAG_OPACITY),
  }));
  const maskBottomStyle = useAnimatedStyle(() => {
    const r = region.value;
    return {
      top: (r.y + r.height) * windowHeight,
      opacity: 1 - dragging.value * (1 - MASK_DRAG_OPACITY),
    };
  });
  const maskLeftStyle = useAnimatedStyle(() => {
    const r = region.value;
    return {
      top: r.y * windowHeight,
      width: r.x * windowWidth,
      height: r.height * windowHeight,
      opacity: 1 - dragging.value * (1 - MASK_DRAG_OPACITY),
    };
  });
  const maskRightStyle = useAnimatedStyle(() => {
    const r = region.value;
    return {
      top: r.y * windowHeight,
      left: (r.x + r.width) * windowWidth,
      height: r.height * windowHeight,
      opacity: 1 - dragging.value * (1 - MASK_DRAG_OPACITY),
    };
  });

  const handleStyles = useCornerHandleStyles(region, windowWidth, windowHeight);

  /** Move the frame onto a still's problem (`fitToContent`), gliding unless motion is reduced. */
  const fitRegion = useCallback((next: ScanRegion) => {
    const duration = motionMs(Motion.duration.short, reduceMotion);
    runOnUI((requested: ScanRegion) => {
      const target = clampScanRegion(requested, insetSv.value);
      region.value = duration > 0 ? withTiming(target, { duration }) : target;
      runOnJS(pushRegion)(target);
    })(next);
  }, [insetSv, pushRegion, reduceMotion, region]);

  const resetRegion = useCallback((next?: ScanRegion) => {
    runOnUI((requested?: ScanRegion) => {
      const nextRegion = clampScanRegion(
        requested ?? {
          x: (1 - DEFAULT_REGION_WIDTH) / 2,
          y: (1 - DEFAULT_REGION_HEIGHT) / 2,
          width: DEFAULT_REGION_WIDTH,
          height: DEFAULT_REGION_HEIGHT,
        },
        insetSv.value,
      );
      region.value = nextRegion;
      runOnJS(pushRegion)(nextRegion);
    })(next);
  }, [insetSv, pushRegion, region]);

  const scaleRegion = useCallback((factor: number) => {
    adjust();
    runOnUI(() => {
      const next = scaleScanRegion(region.value, factor, insetSv.value);
      region.value = next;
      runOnJS(pushRegion)(next);
    })();
  }, [adjust, insetSv, pushRegion, region]);
  const growRegion = useCallback(() => scaleRegion(1.08), [scaleRegion]);
  const shrinkRegion = useCallback(() => scaleRegion(0.92), [scaleRegion]);

  const readRegion = useCallback((): ScanRegion => region.value, [region]);
  const adjustments = useCallback(() => adjustCount.current, []);

  const resetZoom = useCallback(() => {
    zoomSv.value = 0;
    lastPushedZoom.value = 0;
    onZoom(0);
  }, [lastPushedZoom, onZoom, zoomSv]);

  return {
    regionGesture,
    cornerTL,
    cornerTR,
    cornerBL,
    cornerBR,
    regionStyle,
    maskTopStyle,
    maskBottomStyle,
    maskLeftStyle,
    maskRightStyle,
    ...handleStyles,
    resetRegion,
    fitRegion,
    growRegion,
    shrinkRegion,
    readRegion,
    adjustments,
    resetZoom,
  };
}
