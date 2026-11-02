import { StyleSheet } from "react-native";
import { act, render } from "@testing-library/react-native";

import { LiveTalkOrb } from "@/features/speech/components/LiveTalkOrb";
import type { LiveTalkPhase } from "@/features/speech/model/liveTalkLogic";
import { lightTheme } from "@/lib/theme";

jest.mock("expo-linear-gradient", () => {
  const { View } = jest.requireActual("react-native") as typeof import("react-native");
  return { LinearGradient: View };
});

type Transform = Record<string, number>[];

function transformOf(view: Awaited<ReturnType<typeof render>>, testID: string): Transform {
  return (StyleSheet.flatten(view.getByTestId(testID).props.style).transform ?? []) as Transform;
}

function faceScale(view: Awaited<ReturnType<typeof render>>): number {
  return transformOf(view, "live-talk-orb-face").find((step) => "scale" in step)?.scale ?? 1;
}

function eyesScaleY(view: Awaited<ReturnType<typeof render>>): number {
  return transformOf(view, "live-talk-orb-eyes").find((step) => "scaleY" in step)?.scaleY ?? 1;
}

/** The test reanimated mock lands each animation on its first target; a render reads it. */
async function orb(phase: LiveTalkPhase, speaking: boolean, reduceMotion = false) {
  const element = (p: LiveTalkPhase, s: boolean) => (
    <LiveTalkOrb theme={lightTheme} phase={p} speaking={s} reduceMotion={reduceMotion} />
  );
  const view = await render(element(phase, speaking));
  await view.rerender(element(phase, speaking));
  return { view, element };
}

describe("LiveTalkOrb", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });
  afterEach(() => {
    jest.useRealTimers();
  });

  it("is only the face: no halo, glow or ring around it", async () => {
    const { view } = await orb("recording", false);
    const stage = view.getByTestId("live-talk-orb-listen");
    expect(stage.children).toHaveLength(1);
    expect(view.getByTestId("live-talk-orb-face")).toBe(stage.children[0]);
  });

  it.each<LiveTalkPhase>(["idle", "thinking", "recording"])(
    "holds the face still while %s, however long it waits",
    async (phase) => {
      const { view, element } = await orb(phase, false);
      expect(faceScale(view)).toBe(1);
      await act(async () => {
        jest.advanceTimersByTime(20_000);
      });
      await view.rerender(element(phase, false));
      expect(faceScale(view)).toBe(1);
    },
  );

  it("swells only while the voice plays, and settles back to rest after", async () => {
    const { view, element } = await orb("speaking", false);
    // The words can arrive before the audio: no voice yet, no motion.
    expect(faceScale(view)).toBe(1);

    await view.rerender(element("speaking", true));
    await view.rerender(element("speaking", true));
    expect(faceScale(view)).toBeGreaterThan(1);
    expect(faceScale(view)).toBeLessThanOrEqual(1.06);

    await view.rerender(element("recording", false));
    await view.rerender(element("recording", false));
    expect(faceScale(view)).toBe(1);
  });

  it("keeps the eyes centred, with no gaze offset", async () => {
    const { view } = await orb("recording", false);
    const eyes = transformOf(view, "live-talk-orb-eyes");
    expect(eyes.some((step) => "translateX" in step || "translateY" in step)).toBe(false);
  });

  it("blinks within six seconds, by its own schedule", async () => {
    const { view, element } = await orb("recording", false);
    expect(eyesScaleY(view)).toBe(1);
    await act(async () => {
      jest.advanceTimersByTime(6_000);
    });
    await view.rerender(element("recording", false));
    expect(eyesScaleY(view)).toBeLessThan(0.5);
  });

  it("never moves or blinks with reduce motion on", async () => {
    const { view, element } = await orb("speaking", true, true);
    expect(faceScale(view)).toBe(1);
    await act(async () => {
      jest.advanceTimersByTime(30_000);
    });
    await view.rerender(element("speaking", true));
    expect(faceScale(view)).toBe(1);
    expect(eyesScaleY(view)).toBe(1);
  });
});
