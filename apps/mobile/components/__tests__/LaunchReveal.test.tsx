import { act, render } from "@testing-library/react-native";

import appJson from "../../app.json";
import {
  LaunchReveal,
  REDUCED_FADE_MS,
  SETTING_WAIT_MS,
  SPLASH_BACKGROUND,
  SPLASH_ICON_SIZE,
} from "@/components/LaunchReveal";

/** The OS Reduce Motion setting: `null` while it is still being read. */
const mockReduceMotion = jest.fn<boolean | null, []>(() => false);
jest.mock("@/lib/motion", () => ({ useReduceMotionSetting: () => mockReduceMotion() }));

/** The native splash: gone once `goneNow()` is called. */
const mockSplash = { gone: false, listeners: new Set<() => void>() };
jest.mock("@/lib/launchSplash", () => ({
  launchSplashHidden: () => mockSplash.gone,
  subscribeLaunchSplashHidden: (listener: () => void) => {
    mockSplash.listeners.add(listener);
    return () => mockSplash.listeners.delete(listener);
  },
}));

async function goneNow(): Promise<void> {
  await act(async () => {
    mockSplash.gone = true;
    mockSplash.listeners.forEach((listener) => listener());
  });
}

type TimingConfig = { duration?: number; reduceMotion?: string };
const reanimated = jest.requireMock("react-native-reanimated") as {
  withTiming: (value: number, config?: TimingConfig, done?: (finished?: boolean) => void) => number;
};
/** Every timing the reveal starts; each one finishes at once. */
let timings: TimingConfig[] = [];

beforeEach(() => {
  mockSplash.gone = false;
  mockSplash.listeners.clear();
  mockReduceMotion.mockReturnValue(false);
  timings = [];
  jest.spyOn(reanimated, "withTiming").mockImplementation((value, config, done) => {
    timings.push(config ?? {});
    done?.(true);
    return value;
  });
});

afterEach(() => {
  jest.restoreAllMocks();
  jest.useRealTimers();
});

type SplashOptions = { image: string; imageWidth?: number; backgroundColor: string; dark?: { backgroundColor?: string } };

function splashConfig(): SplashOptions {
  const entry = (appJson.expo.plugins as unknown[]).find(
    (plugin): plugin is [string, SplashOptions] => Array.isArray(plugin) && plugin[0] === "expo-splash-screen",
  );
  if (!entry) throw new Error("app.json has no expo-splash-screen plugin");
  return entry[1];
}

const HIDDEN = { includeHiddenElements: true };

it("draws the native splash again: its icon, size and both page colours", () => {
  // A reveal that differs from the native splash would jump on the first frame.
  const splash = splashConfig();
  expect(splash.image).toBe("./assets/images/splash-icon.png");
  expect(splash.imageWidth ?? 100).toBe(SPLASH_ICON_SIZE);
  expect(splash.backgroundColor).toBe(SPLASH_BACKGROUND.light);
  expect(splash.dark?.backgroundColor).toBe(SPLASH_BACKGROUND.dark);
});

it("covers the first frame, touch-through, until the splash goes", async () => {
  const { getByTestId } = await render(<LaunchReveal />);
  // Hidden from VoiceOver on purpose: it is the splash, not content.
  const page = getByTestId("launch-reveal", HIDDEN);
  expect(page.props.pointerEvents).toBe("none");
  expect(page).toHaveStyle({ backgroundColor: SPLASH_BACKGROUND.light });
  expect(timings).toEqual([]);
});

it("plays the full reveal when the splash goes, then leaves the app", async () => {
  const { queryByTestId } = await render(<LaunchReveal />);
  await goneNow();
  expect(timings.map((timing) => timing.duration)).toEqual([200, 360, 260, 320]);
  // The motion follows Reanimated's own reading of the OS setting.
  expect(timings.every((timing) => timing.reduceMotion === undefined)).toBe(true);
  expect(queryByTestId("launch-reveal", HIDDEN)).toBeNull();
});

it("waits for the OS to answer Reduce Motion, so a guess never starts the motion", async () => {
  mockReduceMotion.mockReturnValue(null);
  const { rerender, queryByTestId } = await render(<LaunchReveal />);
  await goneNow();
  expect(timings).toEqual([]);
  expect(queryByTestId("launch-reveal", HIDDEN)).not.toBeNull();

  // Reduce Motion on: a real short fade, never Reanimated's cut to the end.
  mockReduceMotion.mockReturnValue(true);
  await rerender(<LaunchReveal />);
  expect(timings).toEqual([{ duration: REDUCED_FADE_MS, reduceMotion: "never" }]);
  expect(queryByTestId("launch-reveal", HIDDEN)).toBeNull();
});

it("takes the short fade if the OS never answers, rather than staying over the app", async () => {
  jest.useFakeTimers();
  mockReduceMotion.mockReturnValue(null);
  const { queryByTestId } = await render(<LaunchReveal />);
  await goneNow();
  await act(async () => jest.advanceTimersByTime(SETTING_WAIT_MS - 1));
  expect(timings).toEqual([]);
  await act(async () => jest.advanceTimersByTime(1));
  expect(timings).toEqual([{ duration: REDUCED_FADE_MS, reduceMotion: "never" }]);
  expect(queryByTestId("launch-reveal", HIDDEN)).toBeNull();
});

it("starts at once when mounted after the splash went", async () => {
  mockSplash.gone = true;
  mockReduceMotion.mockReturnValue(true);
  const { queryByTestId } = await render(<LaunchReveal />);
  expect(timings).toEqual([{ duration: REDUCED_FADE_MS, reduceMotion: "never" }]);
  expect(queryByTestId("launch-reveal", HIDDEN)).toBeNull();
});
