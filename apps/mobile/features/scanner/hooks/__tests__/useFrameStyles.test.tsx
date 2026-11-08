/**
 * The dimmed mask around the crop frame. The right mask had a start and no width, so a
 * frame pulled in from the right left the camera undimmed beside it (phone, 2026-11-08).
 */
import { renderHook } from "@testing-library/react-native";
import type { SharedValue } from "react-native-reanimated";

import { useFrameStyles } from "@/features/scanner/hooks/useFrameStyles";
import type { ScanRegion } from "@/lib/math/scannerRegion";

const W = 400;
const H = 800;

type Box = { top?: number; left?: number; width?: number; height?: number };

async function masks(region: ScanRegion) {
  const shared = { value: region } as SharedValue<ScanRegion>;
  const dragging = { value: 0 } as SharedValue<number>;
  const { result } = await renderHook(() => useFrameStyles(shared, dragging, W, H));
  const styles = result.current as unknown as Record<string, Box>;
  return { left: styles.maskLeftStyle!, right: styles.maskRightStyle!, top: styles.maskTopStyle!, bottom: styles.maskBottomStyle! };
}

it.each<[string, ScanRegion]>([
  ["pulled in from the right", { x: 0.06, y: 0.35, width: 0.75, height: 0.24 }],
  ["pulled in from the left", { x: 0.3, y: 0.35, width: 0.64, height: 0.24 }],
  ["centred", { x: 0.1, y: 0.2, width: 0.8, height: 0.4 }],
])("dims the whole row beside a frame %s", async (_name, region) => {
  const { left, right } = await masks(region);
  const frameLeft = region.x * W;
  const frameRight = (region.x + region.width) * W;
  expect(left.width).toBeCloseTo(frameLeft);
  expect(right.left).toBeCloseTo(frameRight);
  expect(right.width).toBeCloseTo(W - frameRight);
  expect(right.top).toBeCloseTo(left.top!);
  expect(right.height).toBeCloseTo(region.height * H);
});

it("leaves no right mask for a frame that reaches the right edge", async () => {
  const { right } = await masks({ x: 0.2, y: 0.3, width: 0.8, height: 0.3 });
  expect(right.width).toBe(0);
});
