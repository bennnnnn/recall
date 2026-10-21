import * as Location from "expo-location";

import { getDeviceLocationLabel, requestDeviceGeo } from "@/lib/deviceLocation";

jest.mock("@/lib/expoRuntime", () => ({ canUseDeviceLocation: () => true }));
jest.mock("expo-location", () => ({
  Accuracy: { Balanced: 3 },
  getForegroundPermissionsAsync: jest.fn(),
  requestForegroundPermissionsAsync: jest.fn(),
  getLastKnownPositionAsync: jest.fn(),
  getCurrentPositionAsync: jest.fn(),
  reverseGeocodeAsync: jest.fn(),
}));

const mocked = Location as unknown as Record<
  | "getForegroundPermissionsAsync"
  | "requestForegroundPermissionsAsync"
  | "getLastKnownPositionAsync"
  | "getCurrentPositionAsync"
  | "reverseGeocodeAsync",
  jest.Mock
>;
const at = (latitude: number, longitude: number) => ({ coords: { latitude, longitude } });
const oakland = [{ city: "Oakland", region: "CA", country: "United States" }];
const never = () => new Promise<never>(() => undefined);

describe("requestDeviceGeo", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    mocked.getForegroundPermissionsAsync.mockResolvedValue({ status: "granted", canAskAgain: true });
    mocked.reverseGeocodeAsync.mockResolvedValue(oakland);
  });
  afterEach(() => {
    jest.useRealTimers();
  });

  it("answers a chat send from a recent fix without asking for a new one", async () => {
    mocked.getLastKnownPositionAsync.mockResolvedValue(at(37.8, -122.27));
    await expect(requestDeviceGeo({ quick: true })).resolves.toEqual({
      status: "granted",
      geo: { label: "Oakland, CA, United States", latitude: 37.8, longitude: -122.27 },
    });
    expect(mocked.getLastKnownPositionAsync).toHaveBeenCalledWith({ maxAge: 300_000, requiredAccuracy: 500 });
    expect(mocked.getCurrentPositionAsync).not.toHaveBeenCalled();
  });

  it("asks for a new fix when there is no recent one", async () => {
    mocked.getLastKnownPositionAsync.mockResolvedValue(null);
    mocked.getCurrentPositionAsync.mockResolvedValue(at(37.8, -122.27));
    const result = await requestDeviceGeo({ quick: true });
    expect(result).toMatchObject({ status: "granted", geo: { latitude: 37.8 } });
    expect(mocked.getCurrentPositionAsync).toHaveBeenCalledWith({ accuracy: 3 });
  });

  it("goes without a fix when none comes within five seconds", async () => {
    mocked.getLastKnownPositionAsync.mockRejectedValue(new Error("no provider"));
    mocked.getCurrentPositionAsync.mockReturnValue(never());
    const reading = requestDeviceGeo({ quick: true });
    await jest.advanceTimersByTimeAsync(4_999);
    let settled = false;
    void reading.then(() => { settled = true; });
    await Promise.resolve();
    expect(settled).toBe(false);
    await jest.advanceTimersByTimeAsync(1);
    await expect(reading).resolves.toEqual({ status: "no_fix" });
  });

  it("sends the coordinates alone when the place name is slow", async () => {
    mocked.getLastKnownPositionAsync.mockResolvedValue(at(37.8, -122.27));
    mocked.reverseGeocodeAsync.mockReturnValue(never());
    const reading = requestDeviceGeo({ quick: true });
    await jest.advanceTimersByTimeAsync(1_500);
    await expect(reading).resolves.toEqual({
      status: "granted",
      geo: { label: null, latitude: 37.8, longitude: -122.27 },
    });
  });

  it("waits for a new fix and its place name for Settings", async () => {
    mocked.getCurrentPositionAsync.mockResolvedValue(at(37.8, -122.27));
    await expect(getDeviceLocationLabel()).resolves.toBe("Oakland, CA, United States");
    expect(mocked.getLastKnownPositionAsync).not.toHaveBeenCalled();
  });

  it("still reports a refused permission without reading a position", async () => {
    mocked.getForegroundPermissionsAsync.mockResolvedValue({ status: "denied", canAskAgain: false });
    await expect(requestDeviceGeo({ quick: true })).resolves.toEqual({ status: "blocked" });
    expect(mocked.getLastKnownPositionAsync).not.toHaveBeenCalled();
  });
});
