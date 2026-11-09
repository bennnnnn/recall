/* eslint-disable react-hooks/immutability -- Reanimated shared values mutate `.value` in gestures. */
import { useCallback, useEffect, useMemo, useRef } from "react";
import { Gesture } from "react-native-gesture-handler";
import {
  runOnJS,
  runOnUI,
  useAnimatedReaction,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";

import { Motion, motionMs } from "@/lib/motion";
import {
  type ScanChromeInset,
  type ScanHandle,
  type ScanRegion,
  clampScanRegion,
  defaultScanRegion,
  DEFAULT_REGION_HEIGHT,
  DEFAULT_REGION_WIDTH,
  resizeScanRegion,
  SCAN_HANDLES,
  scaleScanRegion,
  translateScanRegion,
  zoomFromPinch,
} from "@/lib/math/scannerRegion";
import { useFrameHandleStyles, useFrameStyles } from "@/features/scanner/hooks/useFrameStyles";

const ZOOM_PUSH_DELTA = 0.02;

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
  const resizeBase = useSharedValue<ScanRegion>(defaultScanRegion(inset));
  // A handle and the frame never move it at once: with a finger on each, both wrote the frame
  // and it jumped between the two. The handle dragging it (-1: none), the frame gestures
  // holding it, and whether the pan and the pinch each took a hold.
  const handleOwner = useSharedValue(-1);
  const frameHolds = useSharedValue(0);
  const panHolds = useSharedValue(false);
  const pinchHolds = useSharedValue(false);

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
  const pushRegion = useCallback((next: ScanRegion) => onRegionChange?.(next), [onRegionChange]);
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
  );

  /* eslint-disable react-hooks/refs -- the gesture callbacks read refs on touch, not in render */
  const pinchGesture = useMemo(
    () =>
      Gesture.Pinch()
        .onBegin(() => {
          pinchStartZoom.value = zoomSv.value;
          pinchStartRegion.value = region.value;
        })
        // The mask lightens once a gesture is really under way, so a tap does not flash it.
        .onStart(() => {
          dragging.value = 1;
          if (!previewSv.value || handleOwner.value >= 0) return;
          pinchHolds.value = true;
          frameHolds.value += 1;
          runOnJS(adjust)();
        })
        .onUpdate((e) => {
          if (previewSv.value) {
            if (pinchHolds.value) region.value = scaleScanRegion(pinchStartRegion.value, e.scale, insetSv.value);
            return;
          }
          zoomSv.value = zoomFromPinch(pinchStartZoom.value, e.scale);
        })
        .onEnd(() => {
          dragging.value = withTiming(0, { duration: dragDuration });
          if (!previewSv.value) runOnJS(onZoom)(zoomSv.value);
          if (!pinchHolds.value) return;
          pinchHolds.value = false;
          frameHolds.value -= 1;
          runOnJS(pushRegion)(region.value);
        }),
    [
      adjust,
      dragDuration,
      dragging,
      frameHolds,
      handleOwner,
      insetSv,
      onZoom,
      pinchHolds,
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
        .onStart((e) => {
          if (handleOwner.value >= 0) return;
          panHolds.value = true;
          frameHolds.value += 1;
          dragging.value = 1;
          panBase.value = region.value;
          panOriginX.value = e.translationX;
          panOriginY.value = e.translationY;
          runOnJS(adjust)();
        })
        .onUpdate((e) => {
          if (!panHolds.value) return;
          const dx = (e.translationX - panOriginX.value) / windowWidth;
          const dy = (e.translationY - panOriginY.value) / windowHeight;
          region.value = translateScanRegion(panBase.value, dx, dy, insetSv.value);
        })
        .onEnd(() => {
          if (!panHolds.value) return;
          panHolds.value = false;
          frameHolds.value -= 1;
          dragging.value = withTiming(0, { duration: dragDuration });
          runOnJS(pushRegion)(region.value);
        }),
    [
      adjust,
      dragDuration,
      dragging,
      frameHolds,
      handleOwner,
      insetSv,
      panBase,
      panHolds,
      panOriginX,
      panOriginY,
      pushRegion,
      region,
      windowHeight,
      windowWidth,
    ],
  );

  const makeHandleGesture = useCallback(
    (handle: ScanHandle, index: number) =>
      Gesture.Pan()
        .maxPointers(1)
        .onStart((e) => {
          if (frameHolds.value > 0 || handleOwner.value >= 0) return;
          handleOwner.value = index;
          dragging.value = 1;
          resizeBase.value = region.value;
          panOriginX.value = e.translationX;
          panOriginY.value = e.translationY;
          runOnJS(adjust)();
        })
        .onUpdate((e) => {
          if (handleOwner.value !== index) return;
          const dx = (e.translationX - panOriginX.value) / windowWidth;
          const dy = (e.translationY - panOriginY.value) / windowHeight;
          region.value = resizeScanRegion(resizeBase.value, handle, dx, dy, insetSv.value);
        })
        .onEnd(() => {
          if (handleOwner.value !== index) return;
          handleOwner.value = -1;
          dragging.value = withTiming(0, { duration: dragDuration });
          runOnJS(pushRegion)(region.value);
        }),
    [
      adjust,
      resizeBase,
      dragDuration,
      dragging,
      frameHolds,
      handleOwner,
      insetSv,
      panOriginX,
      panOriginY,
      pushRegion,
      region,
      windowHeight,
      windowWidth,
    ],
  );

  const handleGestures = useMemo(() => SCAN_HANDLES.map(makeHandleGesture), [makeHandleGesture]);
  /* eslint-enable react-hooks/refs */

  const tapGesture = useMemo(
    () =>
      Gesture.Tap().maxDistance(10).onEnd((e) => {
        const r = region.value;
        runOnJS(tap)({ x: r.x * windowWidth + e.x, y: r.y * windowHeight + e.y });
      }),
    [region, tap, windowHeight, windowWidth],
  );

  const regionGesture = useMemo(
    () => Gesture.Simultaneous(pinchGesture, panGesture, tapGesture),
    [pinchGesture, panGesture, tapGesture],
  );

  const frameStyles = useFrameStyles(region, dragging, windowWidth, windowHeight);
  const handleStyles = useFrameHandleStyles(region, windowWidth, windowHeight);
  // Each edge and corner of the frame, with what it draws and does.
  const handles = SCAN_HANDLES.map((handle, index) => ({ handle, gesture: handleGestures[index]!, style: handleStyles[handle] }));

  // Read when a fit starts: a fit that changed with Reduce Motion reset the student's frame.
  const fitMsRef = useRef(motionMs(Motion.duration.short, reduceMotion));
  useEffect(() => {
    fitMsRef.current = motionMs(Motion.duration.short, reduceMotion);
  }, [reduceMotion]);
  /** Move the frame onto a still's problem (`fitToContent`), gliding unless motion is reduced. */
  const fitRegion = useCallback((next: ScanRegion) => {
    const duration = fitMsRef.current;
    runOnUI((requested: ScanRegion) => {
      const target = clampScanRegion(requested, insetSv.value);
      region.value = duration > 0 ? withTiming(target, { duration }) : target;
      runOnJS(pushRegion)(target);
    })(next);
  }, [insetSv, pushRegion, region]);

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
      // A reset (open, retake, a new still) starts with nothing holding the frame.
      handleOwner.value = -1;
      frameHolds.value = 0;
      panHolds.value = pinchHolds.value = false;
      runOnJS(pushRegion)(nextRegion);
    })(next);
  }, [frameHolds, handleOwner, insetSv, panHolds, pinchHolds, pushRegion, region]);

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
    handles,
    ...frameStyles,
    resetRegion,
    fitRegion,
    growRegion,
    shrinkRegion,
    readRegion,
    adjustments,
    resetZoom,
  };
}
