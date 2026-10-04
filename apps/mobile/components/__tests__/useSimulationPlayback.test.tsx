import { act, renderHook } from "@testing-library/react-native";
import { AppState, type AppStateStatus } from "react-native";
import * as Reanimated from "react-native-reanimated";

import { useSimulationPlayback } from "@/components/rich/simulation/useSimulationPlayback";

describe("native scene playback lifecycle", () => {
  let onState: (state: AppStateStatus) => void;
  let remove: jest.Mock;
  let timing: jest.SpyInstance;
  let completions: ((finished?: boolean) => void)[];

  beforeEach(() => {
    completions = [];
    remove = jest.fn();
    jest.spyOn(AppState, "addEventListener").mockImplementation((_event, listener) => {
      onState = listener;
      return { remove };
    });
    timing = jest.spyOn(Reanimated, "withTiming").mockImplementation((target, _config, callback) => {
      if (callback) completions.push(callback);
      // Leave the animation partway through to exercise resume and replacement.
      return 0.25 as typeof target;
    });
  });
  afterEach(() => jest.restoreAllMocks());

  it("restarts a replacement scene and ignores the old completion", async () => {
    const { result, rerender } = await renderHook(
      ({ key }) => useSimulationPlayback(key, true, false, 8000),
      { initialProps: { key: "first" } },
    );
    result.current.progress.value = 0.6;
    await rerender({ key: "second" });
    expect(timing.mock.calls.at(-1)?.[1].duration).toBe(8000);
    await act(() => completions[0](true));
    expect(result.current.isPlaying).toBe(true);
    await act(() => completions.at(-1)!(true));
    expect(result.current.isPlaying).toBe(false);
  });

  it("pauses in the background, resumes remaining time, and removes its listener", async () => {
    const { result, unmount } = await renderHook(() =>
      useSimulationPlayback("orbit", true, false, 8000),
    );
    await act(() => onState("inactive"));
    await act(() => onState("background"));
    expect(result.current.isPlaying).toBe(false);
    await act(() => onState("active"));
    expect(timing.mock.calls.at(-1)?.[1].duration).toBe(6000);
    expect(result.current.isPlaying).toBe(true);
    await unmount();
    expect(remove).toHaveBeenCalledTimes(1);
    expect(Reanimated.cancelAnimation).toHaveBeenCalledWith(result.current.progress);
  });

  it("keeps a manually paused scene paused after returning to the app", async () => {
    const { result } = await renderHook(() => useSimulationPlayback("orbit", true, false, 8000));
    await act(() => result.current.pause());
    await act(() => onState("background"));
    await act(() => onState("active"));
    expect(timing).toHaveBeenCalledTimes(1);
    expect(result.current.isPlaying).toBe(false);
  });

  it("cancels and resets the first sample when Reduce Motion is enabled", async () => {
    const { result, rerender } = await renderHook(
      ({ reduce }) => useSimulationPlayback("orbit", true, reduce, 8000),
      { initialProps: { reduce: false } },
    );
    await rerender({ reduce: true });
    expect(result.current.progress.value).toBe(0);
    expect(result.current.isPlaying).toBe(false);
    expect(timing).toHaveBeenCalledTimes(1);
  });
});
