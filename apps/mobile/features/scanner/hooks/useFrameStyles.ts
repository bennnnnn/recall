import { Platform } from "react-native";
import { type SharedValue, useAnimatedStyle } from "react-native-reanimated";

import type { ScanHandle, ScanRegion } from "@/lib/math/scannerRegion";

/** theme.scrim is ~0.40 idle; multiply by this while dragging → ~0.25. */
const MASK_DRAG_OPACITY = 0.625;

/** How far a handle's touch area reaches outside the frame, in points. */
const REACH_OUT = 28;
/** How far it reaches inside: at most this, and a fifth of the side, so a small frame still moves. */
const REACH_IN = 16;
/**
 * Android takes a drag that starts this near the screen's left or right edge as Back (its
 * default inset), which closed the scanner and dropped the shot: no handle reaches there.
 */
const SIDE_GUARD = Platform.OS === "android" ? 24 : 0;

/**
 * One handle's touch area: an edge's runs along that side between the corners; a corner's
 * holds the corner. Each reaches well outside the frame and a little inside, so the border
 * is easy to grab and the middle still moves the frame.
 */
function useHandleStyle(region: SharedValue<ScanRegion>, windowWidth: number, windowHeight: number, handle: ScanHandle) {
  return useAnimatedStyle(() => {
    const r = region.value;
    const left = r.x * windowWidth;
    const top = r.y * windowHeight;
    const right = (r.x + r.width) * windowWidth;
    const bottom = (r.y + r.height) * windowHeight;
    const inX = Math.min(REACH_IN, (right - left) / 5);
    const inY = Math.min(REACH_IN, (bottom - top) / 5);
    const x0 = Math.max(SIDE_GUARD, handle.includes("l") ? left - REACH_OUT : handle.includes("r") ? right - inX : left + inX);
    const x1 = Math.min(windowWidth - SIDE_GUARD, handle.includes("l") ? left + inX : handle.includes("r") ? right + REACH_OUT : right - inX);
    const y0 = handle.includes("t") ? top - REACH_OUT : handle.includes("b") ? bottom - inY : top + inY;
    const y1 = handle.includes("t") ? top + inY : handle.includes("b") ? bottom + REACH_OUT : bottom - inY;
    return { left: x0, top: y0, width: Math.max(0, x1 - x0), height: Math.max(0, y1 - y0) };
  });
}

/** The touch areas of the frame's four edges and four corners, by handle. */
export function useFrameHandleStyles(region: SharedValue<ScanRegion>, windowWidth: number, windowHeight: number) {
  return {
    tl: useHandleStyle(region, windowWidth, windowHeight, "tl"),
    t: useHandleStyle(region, windowWidth, windowHeight, "t"),
    tr: useHandleStyle(region, windowWidth, windowHeight, "tr"),
    r: useHandleStyle(region, windowWidth, windowHeight, "r"),
    br: useHandleStyle(region, windowWidth, windowHeight, "br"),
    b: useHandleStyle(region, windowWidth, windowHeight, "b"),
    bl: useHandleStyle(region, windowWidth, windowHeight, "bl"),
    l: useHandleStyle(region, windowWidth, windowHeight, "l"),
  };
}

/** The frame, and the dimmed mask around it (lighter while it is dragged). */
export function useFrameStyles(region: SharedValue<ScanRegion>, dragging: SharedValue<number>, windowWidth: number, windowHeight: number) {
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
  // Its own width, as the left mask has: from `left` alone it was zero wide, and the
  // camera showed undimmed beside a frame pulled in from the right.
  const maskRightStyle = useAnimatedStyle(() => {
    const r = region.value;
    return {
      top: r.y * windowHeight,
      left: (r.x + r.width) * windowWidth,
      width: Math.max(0, 1 - r.x - r.width) * windowWidth,
      height: r.height * windowHeight,
      opacity: 1 - dragging.value * (1 - MASK_DRAG_OPACITY),
    };
  });
  return { regionStyle, maskTopStyle, maskBottomStyle, maskLeftStyle, maskRightStyle };
}
