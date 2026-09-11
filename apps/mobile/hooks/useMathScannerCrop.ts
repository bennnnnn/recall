import { useCallback, useEffect, useMemo } from "react";
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
  handleHitSize,
  resizeScanRegionFromCorner,
  scaleScanRegion,
  translateScanRegion,
  zoomFromPinch,
} from "@/lib/math/mathScannerRegion";

const ZOOM_PUSH_DELTA = 0.02;
/** theme.scrim is ~0.40 idle; multiply by this while dragging → ~0.25. */
const MASK_DRAG_OPACITY = 0.625;

type Args = {
  windowWidth: number;
  windowHeight: number;
  inset: ScanChromeInset;
  preview: boolean;
  reduceMotion: boolean;
  onZoom: (zoom: number) => void;
};

export function useMathScannerCrop({
  windowWidth,
  windowHeight,
  inset,
  preview,
  reduceMotion,
  onZoom,
}: Args) {
  const region = useSharedValue<ScanRegion>(defaultScanRegion(inset));
  const dragging = useSharedValue(0);
  const previewSv = useSharedValue(preview);
  const zoomSv = useSharedValue(0);
  const lastPushedZoom = useSharedValue(0);
  const insetSv = useSharedValue(inset);
  const pinchStartZoom = useSharedValue(0);
  const pinchStartRegion = useSharedValue<ScanRegion>(region.value);
  const panBase = useSharedValue<ScanRegion>(region.value);
  const panOriginX = useSharedValue(0);
  const panOriginY = useSharedValue(0);
  const cornerBase = useSharedValue<ScanRegion>(region.value);

  useEffect(() => {
    insetSv.value = inset;
    region.value = clampScanRegion(region.value, inset);
  }, [inset, insetSv, region]);

  useEffect(() => {
    previewSv.value = preview;
  }, [preview, previewSv]);

  const dragDuration = motionMs(Motion.duration.standard, reduceMotion);

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
        .onUpdate((e) => {
          if (previewSv.value) {
            region.value = scaleScanRegion(pinchStartRegion.value, e.scale, insetSv.value);
            return;
          }
          zoomSv.value = zoomFromPinch(pinchStartZoom.value, e.scale);
        })
        .onEnd(() => {
          dragging.value = withTiming(0, { duration: dragDuration });
          runOnJS(onZoom)(zoomSv.value);
        }),
    [dragDuration, dragging, insetSv, pinchStartRegion, pinchStartZoom, previewSv, region, zoomSv, onZoom],
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
        })
        .onUpdate((e) => {
          const dx = (e.translationX - panOriginX.value) / windowWidth;
          const dy = (e.translationY - panOriginY.value) / windowHeight;
          region.value = translateScanRegion(panBase.value, dx, dy, insetSv.value);
        })
        .onEnd(() => {
          dragging.value = withTiming(0, { duration: dragDuration });
        }),
    [dragDuration, dragging, insetSv, panBase, panOriginX, panOriginY, region, windowHeight, windowWidth],
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
        })
        .onUpdate((e) => {
          const dx = (e.translationX - panOriginX.value) / windowWidth;
          const dy = (e.translationY - panOriginY.value) / windowHeight;
          region.value = resizeScanRegionFromCorner(
            cornerBase.value,
            corner,
            dx,
            dy,
            insetSv.value,
          );
        })
        .onEnd(() => {
          dragging.value = withTiming(0, { duration: dragDuration });
        }),
    [cornerBase, dragDuration, dragging, insetSv, panOriginX, panOriginY, region, windowHeight, windowWidth],
  );

  const cornerTL = useMemo(() => makeCornerGesture("tl"), [makeCornerGesture]);
  const cornerTR = useMemo(() => makeCornerGesture("tr"), [makeCornerGesture]);
  const cornerBL = useMemo(() => makeCornerGesture("bl"), [makeCornerGesture]);
  const cornerBR = useMemo(() => makeCornerGesture("br"), [makeCornerGesture]);

  const regionGesture = useMemo(
    () => Gesture.Simultaneous(pinchGesture, panGesture),
    [pinchGesture, panGesture],
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

  const handleTLStyle = useAnimatedStyle(() => {
    const r = region.value;
    const hit = handleHitSize(r.width * windowWidth, r.height * windowHeight);
    return {
      left: r.x * windowWidth - hit / 2,
      top: r.y * windowHeight - hit / 2,
      width: hit,
      height: hit,
    };
  });
  const handleTRStyle = useAnimatedStyle(() => {
    const r = region.value;
    const hit = handleHitSize(r.width * windowWidth, r.height * windowHeight);
    return {
      left: (r.x + r.width) * windowWidth - hit / 2,
      top: r.y * windowHeight - hit / 2,
      width: hit,
      height: hit,
    };
  });
  const handleBLStyle = useAnimatedStyle(() => {
    const r = region.value;
    const hit = handleHitSize(r.width * windowWidth, r.height * windowHeight);
    return {
      left: r.x * windowWidth - hit / 2,
      top: (r.y + r.height) * windowHeight - hit / 2,
      width: hit,
      height: hit,
    };
  });
  const handleBRStyle = useAnimatedStyle(() => {
    const r = region.value;
    const hit = handleHitSize(r.width * windowWidth, r.height * windowHeight);
    return {
      left: (r.x + r.width) * windowWidth - hit / 2,
      top: (r.y + r.height) * windowHeight - hit / 2,
      width: hit,
      height: hit,
    };
  });

  const resetRegion = useCallback(() => {
    runOnUI(() => {
      region.value = clampScanRegion(
        {
          x: (1 - DEFAULT_REGION_WIDTH) / 2,
          y: (1 - DEFAULT_REGION_HEIGHT) / 2,
          width: DEFAULT_REGION_WIDTH,
          height: DEFAULT_REGION_HEIGHT,
        },
        insetSv.value,
      );
    })();
  }, [insetSv, region]);

  const growRegion = useCallback(() => {
    runOnUI(() => {
      region.value = scaleScanRegion(region.value, 1.08, insetSv.value);
    })();
  }, [insetSv, region]);

  const shrinkRegion = useCallback(() => {
    runOnUI(() => {
      region.value = scaleScanRegion(region.value, 0.92, insetSv.value);
    })();
  }, [insetSv, region]);

  const readRegion = useCallback((): ScanRegion => region.value, [region]);

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
    handleTLStyle,
    handleTRStyle,
    handleBLStyle,
    handleBRStyle,
    resetRegion,
    growRegion,
    shrinkRegion,
    readRegion,
    resetZoom,
  };
}
