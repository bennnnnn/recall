import React from "react";
import { AppState } from "react-native";
import { act, render } from "@testing-library/react-native";

import { useNetworkStatus } from "@/hooks/useNetworkStatus";
import { resolveConnectivity } from "@/lib/networkProbe";

jest.mock("@react-native-community/netinfo", () => ({
  __esModule: true,
  default: {
    fetch: jest.fn(async () => ({ isConnected: false, isInternetReachable: false })),
    addEventListener: jest.fn(() => () => {}),
  },
}));
jest.mock("@/lib/networkProbe", () => ({ resolveConnectivity: jest.fn() }));

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
    addListener.mockImplementation(defaultAddListener);
  });

  it("stops probing while the app is in the background and resumes on return", async () => {
    await render(<Probe />);
    await act(async () => { await flush(); });
    expect(status).toBe("no_internet");
    const opened = probe.mock.calls.length;
    await elapse(6_000);
    expect(probe.mock.calls.length).toBeGreaterThanOrEqual(opened + 3);

    // Each probe is two requests (our /health and a public 204). Nobody sees
    // the banner in the background, so the 1.5 s loop must not run there.
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
