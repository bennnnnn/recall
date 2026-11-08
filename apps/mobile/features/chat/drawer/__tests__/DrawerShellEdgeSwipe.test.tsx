/**
 * The edge swipe on Android opened the drawer and snapped it shut (Galaxy S23, 2026-11-07).
 * Logged on the phone: the finger landed at x≈6, the first move claimed the drag and marked
 * the drawer open, and the next move decided again, saw it open, and failed the active
 * gesture. Android cancels a failed active gesture; iOS ignores it. A claimed drag stays
 * claimed.
 */
import { render } from "@testing-library/react-native";
import type { ReactNode } from "react";

import { DrawerShell } from "@/features/chat/drawer/DrawerShell";

type Handlers = {
  onBegin: (event: { absoluteX: number; absoluteY: number }) => void;
  onTouchesMove: (
    event: { changedTouches: { absoluteX: number; absoluteY: number }[] },
    manager: { activate: () => void; fail: () => void },
  ) => void;
  onStart: (event: object) => void;
};

const captured: { gesture?: { handlers: Handlers } } = {};

// A Pan builder that keeps its callbacks, so the test can drive them as the gesture system would.
jest.mock("react-native-gesture-handler", () => {
  const recordingPan = () => {
    const handlers: Record<string, unknown> = {};
    const builder: Record<string, unknown> = { handlers };
    const chain: Record<string, unknown> = new Proxy(builder, {
      get: (target, prop: string) => {
        if (prop in target) return target[prop];
        return (fn: unknown) => {
          if (prop.startsWith("on")) handlers[prop] = fn;
          return chain;
        };
      },
    });
    return chain;
  };
  return {
    Gesture: { Pan: recordingPan },
    GestureDetector: ({ gesture, children }: { gesture: { handlers: Handlers }; children: ReactNode }) => {
      captured.gesture = gesture;
      return children;
    },
  };
});
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 1 }));
jest.mock("@/features/chat/drawer/ConversationList", () => ({ ConversationList: () => null }));

const move = (x: number) => ({ changedTouches: [{ absoluteX: x, absoluteY: 400 }] });

it("keeps a claimed edge swipe active when the next move sees the drawer it just opened", async () => {
  await render(<DrawerShell>{null}</DrawerShell>);
  const handlers = captured.gesture!.handlers;
  const manager = { activate: jest.fn(), fail: jest.fn() };

  handlers.onBegin({ absoluteX: 6, absoluteY: 400 });
  handlers.onTouchesMove(move(18), manager); // dx 12: past the 10 pt dead zone, from the edge
  expect(manager.activate).toHaveBeenCalledTimes(1);

  handlers.onStart({}); // the drag starts: the drawer is marked open
  handlers.onTouchesMove(move(24), manager); // dx 18: under the panel-drag distance
  handlers.onTouchesMove(move(60), manager);

  expect(manager.fail).not.toHaveBeenCalled();
});

it("still lets a tap or a vertical scroll go to what is under it", async () => {
  await render(<DrawerShell>{null}</DrawerShell>);
  const handlers = captured.gesture!.handlers;
  const manager = { activate: jest.fn(), fail: jest.fn() };

  handlers.onBegin({ absoluteX: 6, absoluteY: 400 });
  handlers.onTouchesMove({ changedTouches: [{ absoluteX: 8, absoluteY: 440 }] }, manager);

  expect(manager.activate).not.toHaveBeenCalled();
  expect(manager.fail).toHaveBeenCalledTimes(1);
});
