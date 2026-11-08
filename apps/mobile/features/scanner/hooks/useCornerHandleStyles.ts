import { type SharedValue, useAnimatedStyle } from "react-native-reanimated";

import { handleHitSize, type ScanRegion } from "@/lib/math/scannerRegion";

/** One corner handle's hit area, centred on that corner of the frame. */
function useCornerStyle(region: SharedValue<ScanRegion>, windowWidth: number, windowHeight: number, right: boolean, bottom: boolean) {
  return useAnimatedStyle(() => {
    const r = region.value;
    const hit = handleHitSize(r.width * windowWidth, r.height * windowHeight);
    return {
      left: (r.x + (right ? r.width : 0)) * windowWidth - hit / 2,
      top: (r.y + (bottom ? r.height : 0)) * windowHeight - hit / 2,
      width: hit,
      height: hit,
    };
  });
}

/** The crop frame's four corner handles. */
export function useCornerHandleStyles(region: SharedValue<ScanRegion>, windowWidth: number, windowHeight: number) {
  return {
    handleTLStyle: useCornerStyle(region, windowWidth, windowHeight, false, false),
    handleTRStyle: useCornerStyle(region, windowWidth, windowHeight, true, false),
    handleBLStyle: useCornerStyle(region, windowWidth, windowHeight, false, true),
    handleBRStyle: useCornerStyle(region, windowWidth, windowHeight, true, true),
  };
}
