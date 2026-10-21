const mockSplash = { preventAutoHideAsync: jest.fn(async () => true), hide: jest.fn() };
jest.mock("expo-splash-screen", () => mockSplash);

type LaunchSplash = typeof import("@/lib/launchSplash");

function freshSplash(): LaunchSplash {
  let loaded!: LaunchSplash;
  jest.isolateModules(() => {
    loaded = jest.requireActual<LaunchSplash>("@/lib/launchSplash");
  });
  return loaded;
}

beforeEach(() => {
  jest.useFakeTimers();
  jest.clearAllMocks();
  // One frame after the last part is ready.
  globalThis.requestAnimationFrame = (callback: FrameRequestCallback) =>
    setTimeout(() => callback(0), 16) as unknown as number;
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
    jest.advanceTimersByTime(16);
    expect(mockSplash.hide).toHaveBeenCalledTimes(1);

    // Later marks (a retried sign-in, say) leave it alone.
    splash.markLaunchReady("session");
    jest.advanceTimersByTime(2_000);
    expect(mockSplash.hide).toHaveBeenCalledTimes(1);
  });

  it("never holds it longer than a second", () => {
    const splash = freshSplash();
    splash.markLaunchReady("prefs");
    jest.advanceTimersByTime(splash.SPLASH_MAX_MS - 1);
    expect(mockSplash.hide).not.toHaveBeenCalled();
    jest.advanceTimersByTime(1);
    expect(mockSplash.hide).toHaveBeenCalledTimes(1);

    splash.markLaunchReady("session");
    splash.markLaunchReady("fonts");
    jest.advanceTimersByTime(16);
    expect(mockSplash.hide).toHaveBeenCalledTimes(1);
  });
});
