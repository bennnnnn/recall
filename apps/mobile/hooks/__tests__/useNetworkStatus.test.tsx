import React from "react";
import { AppState } from "react-native";
import { act, render } from "@testing-library/react-native";

import NetInfo from "@react-native-community/netinfo";

import { retryDelayMs, useNetworkStatus } from "@/hooks/useNetworkStatus";
import { resolveConnectivity } from "@/lib/networkProbe";

jest.mock("@react-native-community/netinfo", () => ({
  __esModule: true,
  default: {
    fetch: jest.fn(async () => ({ isConnected: false, isInternetReachable: false })),
    addEventListener: jest.fn(() => () => {}),
  },
}));
jest.mock("@/lib/networkProbe", () => ({
  configureNetInfo: jest.fn(),
  resolveConnectivity: jest.fn(),
}));

const probe = resolveConnectivity as jest.MockedFunction<typeof resolveConnectivity>;
let status: ReturnType<typeof useNetworkStatus>["status"];
function Probe() {
  const value = useNetworkStatus();
  React.useLayoutEffect(() => { status = value.status; });
  return null;
}

async function flush() {
  for (let i = 0; i < 10; i += 1) await Promise.resolve();
}

/** Let each probe settle before the next tick, as real time would. */
async function elapse(ms: number) {
  await act(async () => {
    for (let at = 0; at < ms; at += 500) {
      jest.advanceTimersByTime(500);
      await flush();
    }
  });
}

describe("useNetworkStatus offline polling", () => {
  const addListener = AppState.addEventListener as unknown as jest.Mock;
  const defaultAddListener = addListener.getMockImplementation();
  const handlers = new Set<(state: string) => void>();
  const setAppState = async (state: string) => {
    await act(async () => {
      for (const handler of [...handlers]) handler(state);
      await flush();
    });
  };

  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    jest.spyOn(Math, "random").mockReturnValue(0.5); // no jitter: delays are exact
    handlers.clear();
    probe.mockResolvedValue("no_internet");
    addListener.mockImplementation((event: string, handler: (state: string) => void) => {
      if (event !== "change") return { remove: jest.fn() };
      handlers.add(handler);
      return { remove: () => handlers.delete(handler) };
    });
  });
  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
    jest.restoreAllMocks();
    addListener.mockImplementation(defaultAddListener);
  });

  it("stops probing while the app is in the background and resumes on return", async () => {
    await render(<Probe />);
    await act(async () => { await flush(); });
    expect(status).toBe("no_internet");
    const opened = probe.mock.calls.length;
    await elapse(6_000);
    expect(probe.mock.calls.length).toBe(opened + 2); // at 1.5 s and 4.5 s

    // Nobody sees the banner in the background, so the loop must not run there.
    await setAppState("background");
    const atBackground = probe.mock.calls.length;
    await elapse(60_000);
    expect(probe.mock.calls.length).toBe(atBackground);

    probe.mockResolvedValue("online");
    await setAppState("active");
    expect(probe.mock.calls.length).toBeGreaterThan(atBackground);
    expect(status).toBe("online");
  });
});

describe("useNetworkStatus degraded backoff", () => {
  const listen = NetInfo.addEventListener as unknown as jest.Mock;
  let onNetInfo: ((state: object) => void) | null = null;

  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    jest.spyOn(Math, "random").mockReturnValue(0.5);
    probe.mockResolvedValue("api_unreachable");
    // NetInfo calls a new listener at once with the current state, as the library does.
    listen.mockImplementation((handler: (state: object) => void) => {
      onNetInfo = handler;
      handler({ isConnected: true, isInternetReachable: true });
      return () => {
        onNetInfo = null;
      };
    });
  });
  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
    jest.restoreAllMocks();
    listen.mockImplementation(() => () => {});
  });

  it("probes once at start although NetInfo reports twice", async () => {
    await render(<Probe />);
    await act(async () => { await flush(); });
    expect(probe).toHaveBeenCalledTimes(1);
  });

  it("backs off to a minute: ten minutes of an unreachable API cost at most 15 probes", async () => {
    await render(<Probe />);
    await act(async () => { await flush(); });
    await elapse(10 * 60_000);
    expect(status).toBe("api_unreachable");
    // A fixed 1.5 s loop made about 400 here, each to /health and to Google.
    expect(probe.mock.calls.length).toBeLessThanOrEqual(15);
  });

  it("starts the backoff over when the link changes", async () => {
    await render(<Probe />);
    await act(async () => { await flush(); });
    await elapse(5 * 60_000); // deep in the one-minute waits
    const before = probe.mock.calls.length;
    await act(async () => {
      onNetInfo?.({ isConnected: true, isInternetReachable: true });
      await flush();
    });
    await elapse(2_000);
    // The event's own probe, then the first 1.5 s retry.
    expect(probe.mock.calls.length).toBe(before + 2);
  });
});

describe("retryDelayMs", () => {
  it("doubles from 1.5 s to a one-minute cap", () => {
    const exact = () => 0.5;
    expect([0, 1, 2, 3, 4, 5, 6, 10].map((n) => retryDelayMs(n, exact))).toEqual([
      1_500, 3_000, 6_000, 12_000, 24_000, 48_000, 60_000, 60_000,
    ]);
  });

  it("spreads each wait by a fifth either way", () => {
    expect(retryDelayMs(6, () => 0)).toBe(48_000);
    expect(retryDelayMs(6, () => 1)).toBe(72_000);
  });
});
