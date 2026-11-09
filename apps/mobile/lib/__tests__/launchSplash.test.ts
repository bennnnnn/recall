const mockSplash = {
  preventAutoHideAsync: jest.fn(async () => true),
  hide: jest.fn(),
  setOptions: jest.fn(),
};
jest.mock("expo-splash-screen", () => mockSplash);
/** The phone the module loads on: read once, as it loads. */
const mockPhone = { OS: "ios", expoGo: false };
jest.mock("react-native", () => ({
  Platform: {
    get OS() {
      return mockPhone.OS;
    },
  },
}));
jest.mock("@/lib/expoRuntime", () => ({ isExpoGo: () => mockPhone.expoGo }));
const mockReportSplash = jest.fn();
jest.mock("@/lib/sentry", () => ({ reportFailure: mockReportSplash }));

type LaunchSplash = typeof import("@/lib/launchSplash");

function freshSplash(): LaunchSplash {
  let loaded!: LaunchSplash;
  jest.isolateModules(() => {
    loaded = jest.requireActual<LaunchSplash>("@/lib/launchSplash");
  });
  return loaded;
}

const FRAME_MS = 16;

beforeEach(() => {
  jest.useFakeTimers();
  jest.clearAllMocks();
  mockPhone.OS = "ios";
  mockPhone.expoGo = false;
  // One frame after the first screen is ready.
  globalThis.requestAnimationFrame = (callback: FrameRequestCallback) =>
    setTimeout(() => callback(0), FRAME_MS) as unknown as number;
});
afterEach(() => {
  jest.useRealTimers();
});

describe("launch splash", () => {
  it("keeps the splash until the session, the fonts and the preferences are ready", () => {
    const splash = freshSplash();
    expect(mockSplash.preventAutoHideAsync).toHaveBeenCalledTimes(1);

    splash.markLaunchReady("prefs");
    splash.markLaunchReady("session");
    jest.advanceTimersByTime(100);
    expect(mockSplash.hide).not.toHaveBeenCalled();

    splash.markLaunchReady("fonts");
    expect(mockSplash.hide).not.toHaveBeenCalled();
    jest.advanceTimersByTime(FRAME_MS);
    expect(mockSplash.hide).toHaveBeenCalledTimes(1);

    // Later marks (a retried sign-in, say) leave it alone.
    splash.markLaunchReady("session");
    jest.advanceTimersByTime(5_000);
    expect(mockSplash.hide).toHaveBeenCalledTimes(1);
  });

  it("at the deadline, uncovers the screen drawn so far once its fonts gate is open", () => {
    const splash = freshSplash();
    const told = jest.fn();
    splash.subscribeLaunchDeadline(told);
    splash.markLaunchReady("fonts");
    splash.markLaunchReady("prefs");

    jest.advanceTimersByTime(splash.SPLASH_MAX_MS - 1);
    expect(splash.launchDeadlinePassed()).toBe(false);
    expect(mockSplash.hide).not.toHaveBeenCalled();

    // The session still waits on /auth/me: its own loading state shows.
    jest.advanceTimersByTime(1);
    expect(told).toHaveBeenCalledTimes(1);
    expect(splash.launchDeadlinePassed()).toBe(true);
    jest.advanceTimersByTime(FRAME_MS);
    expect(mockSplash.hide).toHaveBeenCalledTimes(1);
  });

  it("with fonts still loading at the deadline, waits for the app to draw without them", () => {
    const splash = freshSplash();
    splash.markLaunchReady("prefs");
    splash.markLaunchReady("session");

    jest.advanceTimersByTime(splash.SPLASH_MAX_MS + 100);
    // No blank frame: the root layout now draws with the system face first.
    expect(mockSplash.hide).not.toHaveBeenCalled();
    splash.markLaunchReady("fonts");
    jest.advanceTimersByTime(FRAME_MS);
    expect(mockSplash.hide).toHaveBeenCalledTimes(1);
  });

  it("goes anyway if the app never draws at all", () => {
    freshSplash();
    jest.advanceTimersByTime(1_999);
    expect(mockSplash.hide).not.toHaveBeenCalled();
    jest.advanceTimersByTime(1);
    expect(mockSplash.hide).toHaveBeenCalledTimes(1);
    jest.advanceTimersByTime(10_000);
    expect(mockSplash.hide).toHaveBeenCalledTimes(1);
  });
});

/** Hide the splash the way a launch does, and say whether the reveal was told. */
function hideOnce(splash: LaunchSplash): jest.Mock {
  const told = jest.fn();
  splash.subscribeLaunchSplashHidden(told);
  for (const part of ["session", "fonts", "prefs"] as const) splash.markLaunchReady(part);
  jest.advanceTimersByTime(FRAME_MS);
  expect(mockSplash.hide).toHaveBeenCalledTimes(1);
  return told;
}

describe("launch splash exit (the reveal starts when the native splash is gone)", () => {
  it("on iOS leaves the native splash as it is, a cut, and starts the reveal with the hide", () => {
    const splash = freshSplash();
    expect(mockSplash.setOptions).not.toHaveBeenCalled();
    const told = hideOnce(splash);
    expect(told).toHaveBeenCalledTimes(1);
    expect(splash.launchSplashHidden()).toBe(true);
  });

  it("on Android turns the native fade off, so the reveal is the only animation", () => {
    // expo-splash-screen fades it out over 400 ms by default there, whatever `fade` says.
    mockPhone.OS = "android";
    const splash = freshSplash();
    expect(mockSplash.setOptions).toHaveBeenCalledWith({ duration: 0 });
    const told = hideOnce(splash);
    expect(told).toHaveBeenCalledTimes(1);
    expect(splash.launchSplashHidden()).toBe(true);
  });

  it("in Expo Go on Android, which keeps its fade, starts the reveal once the fade is over", () => {
    mockPhone.OS = "android";
    mockPhone.expoGo = true;
    const splash = freshSplash();
    expect(mockSplash.setOptions).not.toHaveBeenCalled();
    const told = hideOnce(splash);
    jest.advanceTimersByTime(399);
    expect(told).not.toHaveBeenCalled();
    expect(splash.launchSplashHidden()).toBe(false);
    jest.advanceTimersByTime(1);
    expect(told).toHaveBeenCalledTimes(1);
    expect(splash.launchSplashHidden()).toBe(true);
  });

  it("reports a hide that throws, never throws it on, and still starts the reveal", () => {
    const splash = freshSplash();
    const told = jest.fn();
    splash.subscribeLaunchSplashHidden(told);
    const failure = new Error("no splash view");
    mockSplash.hide.mockImplementationOnce(() => {
      throw failure;
    });
    // Thrown from a frame or a timer, React Native would take it as fatal.
    expect(() => jest.advanceTimersByTime(2_000)).not.toThrow();
    expect(mockReportSplash).toHaveBeenCalledWith("launch_splash_hide", failure);
    expect(told).toHaveBeenCalledTimes(1);
    expect(splash.launchSplashHidden()).toBe(true);
  });

  it("on Android, a setOptions that throws is reported and the reveal waits the native fade out", () => {
    mockPhone.OS = "android";
    const failure = new Error("no splash module");
    mockSplash.setOptions.mockImplementationOnce(() => {
      throw failure;
    });
    // It runs as the module loads: the module still loads, timers and all.
    const splash = freshSplash();
    expect(mockReportSplash).toHaveBeenCalledWith("launch_splash_set_options", failure);
    const told = hideOnce(splash);
    jest.advanceTimersByTime(399);
    expect(told).not.toHaveBeenCalled();
    jest.advanceTimersByTime(1);
    expect(told).toHaveBeenCalledTimes(1);
  });
});
