/**
 * The crop frame's gestures, driven as the gesture system would. A finger on a handle and
 * one on the frame both wrote the frame, each from its own start, and it jumped between
 * the two (local review, 2026-11-08): whichever starts first holds the frame.
 */
import { act, renderHook } from "@testing-library/react-native";

import { useMathScannerCrop } from "@/features/scanner/hooks/useMathScannerCrop";

type Handlers = Record<string, (event?: Record<string, number>) => void>;
type Recorded = { kind: string; handlers: Handlers };

// A gesture builder that keeps its callbacks, so the test can call them.
jest.mock("react-native-gesture-handler", () => {
  const recording = (kind: string) => () => {
    const gesture: Recorded = { kind, handlers: {} };
    const chain: Record<string, unknown> = new Proxy(gesture, {
      get: (target, prop: string) => {
        if (prop in target) return target[prop as keyof Recorded];
        return (fn: unknown) => {
          if (prop.startsWith("on")) gesture.handlers[prop] = fn as Handlers[string];
          return chain;
        };
      },
    });
    return chain;
  };
  return {
    Gesture: {
      Pan: recording("pan"),
      Pinch: recording("pinch"),
      Tap: recording("tap"),
      Simultaneous: (...gestures: Recorded[]) => ({ kind: "simultaneous", gestures }),
    },
  };
});

const ZERO = { top: 0, right: 0, bottom: 0, left: 0 };

async function setup() {
  const { result } = await renderHook(() =>
    useMathScannerCrop({
      windowWidth: 400,
      windowHeight: 800,
      inset: ZERO,
      preview: true,
      reduceMotion: true,
      onZoom: jest.fn(),
    }),
  );
  const crop = result.current;
  const [pinch, pan] = (crop.regionGesture as unknown as { gestures: Recorded[] }).gestures;
  const right = crop.handles.find((h) => h.handle === "r")!.gesture as unknown as Recorded;
  const move = (gesture: Recorded, x: number, y: number) =>
    act(() => gesture.handlers.onUpdate!({ translationX: x, translationY: y }));
  return { crop, pinch: pinch!, pan: pan!, right, move };
}

it("lets the frame move once a handle lets go, and not while it holds the frame", async () => {
  const { crop, pan, right, move } = await setup();
  const start = crop.readRegion();
  await act(() => right.handlers.onStart!({ translationX: 0, translationY: 0 }));
  await act(() => pan.handlers.onStart!({ translationX: 0, translationY: 0 }));
  await move(right, -40, 0);
  await move(pan, 0, 80);
  // The right edge came in 40 pt; the frame did not also slide down.
  const resized = crop.readRegion();
  expect(resized.x).toBeCloseTo(start.x, 10);
  expect(resized.y).toBeCloseTo(start.y, 10);
  expect(resized.width).toBeCloseTo(start.width - 0.1, 10);

  await act(() => pan.handlers.onEnd!());
  await act(() => right.handlers.onEnd!());
  await act(() => pan.handlers.onStart!({ translationX: 0, translationY: 0 }));
  await move(pan, 0, 80);
  expect(crop.readRegion().y).toBeCloseTo(start.y + 0.1, 10);
});

it("keeps a handle still while the frame is being moved", async () => {
  const { crop, pan, right, move } = await setup();
  const start = crop.readRegion();
  await act(() => pan.handlers.onStart!({ translationX: 0, translationY: 0 }));
  await act(() => right.handlers.onStart!({ translationX: 0, translationY: 0 }));
  await move(pan, 0, 80);
  await move(right, -40, 0);
  const moved = crop.readRegion();
  expect(moved.width).toBeCloseTo(start.width, 10);
  expect(moved.y).toBeCloseTo(start.y + 0.1, 10);
});

it("frees the frame on a reset, even after a drag that never ended", async () => {
  const { crop, pan, right, move } = await setup();
  await act(() => pan.handlers.onStart!({ translationX: 0, translationY: 0 }));
  await act(() => crop.resetRegion());
  const start = crop.readRegion();
  await act(() => right.handlers.onStart!({ translationX: 0, translationY: 0 }));
  await move(right, -40, 0);
  expect(crop.readRegion().width).toBeCloseTo(start.width - 0.1, 10);
});
