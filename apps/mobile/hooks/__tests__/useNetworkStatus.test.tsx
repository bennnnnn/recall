import React from "react";
import { AppState } from "react-native";
import NetInfo from "@react-native-community/netinfo";
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
let values: ReturnType<typeof useNetworkStatus>[] = [];
function Probe() {
  const value = useNetworkStatus();
  React.useLayoutEffect(() => {
    status = value.status;
    values.push(value);
  });
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

describe("useNetworkStatus launch probe", () => {
  const addListener = AppState.addEventListener as unknown as jest.Mock;
  const defaultAddListener = addListener.getMockImplementation();
  const netInfoAdd = NetInfo.addEventListener as unknown as jest.Mock;
  const appHandlers = new Set<(state: string) => void>();
  let netInfoListener: ((state: object) => void) | null = null;
  const wifi = { type: "wifi", isConnected: true, isInternetReachable: null };

  const emit = async (state: object) => {
    await act(async () => {
      netInfoListener?.(state);
      await flush();
    });
  };

  beforeEach(() => {
    jest.clearAllMocks();
    values = [];
    appHandlers.clear();
    probe.mockResolvedValue("online");
    (NetInfo.fetch as jest.Mock).mockResolvedValue(wifi);
    // NetInfo hands every new subscriber the current report.
    netInfoAdd.mockImplementation((listener: (state: object) => void) => {
      netInfoListener = listener;
      void Promise.resolve().then(() => listener(wifi));
      return () => { netInfoListener = null; };
    });
    addListener.mockImplementation((event: string, handler: (state: string) => void) => {
      if (event !== "change") return { remove: jest.fn() };
      appHandlers.add(handler);
      return { remove: () => appHandlers.delete(handler) };
    });
  });
  afterEach(() => {
    addListener.mockImplementation(defaultAddListener);
    netInfoAdd.mockImplementation(() => () => {});
  });

  it("probes once at launch although NetInfo repeats its report", async () => {
    await render(<Probe />);
    await act(async () => { await flush(); });
    expect(probe).toHaveBeenCalledTimes(1);

    // The reachability check settling, and the echo of the probe's own refresh.
    await emit({ ...wifi, isInternetReachable: true });
    await emit({ ...wifi, isInternetReachable: true });
    expect(probe).toHaveBeenCalledTimes(1);

    // A new link, or the OS saying the internet is gone, is worth a probe.
    await emit({ type: "cellular", isConnected: true, isInternetReachable: true });
    expect(probe).toHaveBeenCalledTimes(2);
    await emit({ type: "cellular", isConnected: true, isInternetReachable: false });
    expect(probe).toHaveBeenCalledTimes(3);
  });

  it("lets a probe already running answer for a return to the app", async () => {
    let answer!: (status: "online") => void;
    probe.mockImplementationOnce(() => new Promise((resolve) => { answer = resolve; }));
    await render(<Probe />);
    await act(async () => { await flush(); });
    expect(probe).toHaveBeenCalledTimes(1);

    await act(async () => {
      for (const handler of [...appHandlers]) handler("active");
      await flush();
    });
    expect(probe).toHaveBeenCalledTimes(1);

    await act(async () => { answer("online"); await flush(); });
    await act(async () => {
      for (const handler of [...appHandlers]) handler("active");
      await flush();
    });
    expect(probe).toHaveBeenCalledTimes(2);
  });

  it("keeps \"No internet\" on a link that is up with nothing behind it", async () => {
    // A captive portal, or Wi-Fi with its upstream down. Each probe's own
    // NetInfo.refresh() repeats the report to every subscriber.
    const wifiNoInternet = { type: "wifi", isConnected: true, isInternetReachable: false };
    (NetInfo.fetch as jest.Mock).mockResolvedValue(wifiNoInternet);
    netInfoAdd.mockImplementation((listener: (state: object) => void) => {
      netInfoListener = listener;
      void Promise.resolve().then(() => listener(wifiNoInternet));
      return () => { netInfoListener = null; };
    });
    probe.mockImplementation(async () => {
      netInfoListener?.(wifiNoInternet);
      return "no_internet";
    });
    jest.useFakeTimers();
    try {
      await render(<Probe />);
      for (let tick = 0; tick < 6; tick += 1) {
        await act(async () => {
          jest.advanceTimersByTime(1_000);
          await flush();
        });
        expect(status).toBe("no_internet");
      }
    } finally {
      jest.useRealTimers();
    }
  });

  it("drops the banner as soon as the link comes back up, before the probe answers", async () => {
    const airplane = { type: "none", isConnected: false, isInternetReachable: false };
    (NetInfo.fetch as jest.Mock).mockResolvedValue(airplane);
    netInfoAdd.mockImplementation((listener: (state: object) => void) => {
      netInfoListener = listener;
      return () => { netInfoListener = null; };
    });
    probe.mockResolvedValue("no_internet");
    await render(<Probe />);
    await act(async () => { await flush(); });
    expect(status).toBe("no_internet");

    probe.mockImplementation(() => new Promise(() => {}));
    await emit({ type: "wifi", isConnected: true, isInternetReachable: null });
    expect(status).toBe("online");
  });

  it("probes a switch straight from one Wi-Fi network to another", async () => {
    const home = { ...wifi, details: { ipAddress: "192.168.1.20", isConnectionExpensive: false } };
    (NetInfo.fetch as jest.Mock).mockResolvedValue(home);
    netInfoAdd.mockImplementation((listener: (state: object) => void) => {
      netInfoListener = listener;
      return () => { netInfoListener = null; };
    });
    await render(<Probe />);
    await act(async () => { await flush(); });
    expect(probe).toHaveBeenCalledTimes(1);

    await emit(home);
    expect(probe).toHaveBeenCalledTimes(1);
    await emit({ ...wifi, details: { ipAddress: "10.0.0.7", isConnectionExpensive: false } });
    expect(probe).toHaveBeenCalledTimes(2);
  });

  it("keeps the same value when only the app's background state changes", async () => {
    await render(<Probe />);
    await act(async () => { await flush(); });
    const before = values[values.length - 1];
    await act(async () => {
      for (const handler of [...appHandlers]) handler("background");
      await flush();
    });
    expect(values[values.length - 1]).toBe(before);
    expect(before).toEqual({ isOffline: false, status: "online" });
  });
});
