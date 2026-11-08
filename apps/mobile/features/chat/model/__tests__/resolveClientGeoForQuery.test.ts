jest.mock("react-native", () => ({
  Alert: { alert: jest.fn() },
  Linking: { openSettings: jest.fn() },
}));

jest.mock("@/lib/deviceLocation", () => ({
  requestDeviceGeo: jest.fn(),
  hasLocationPermission: jest.fn(),
}));

let mockSessionGeneration = 0;
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSessionGeneration }));

jest.mock("@/lib/places/localPlacesQuery", () => ({
  isGeoQuery: jest.fn(),
  isAmbiguousLocalPlacesQuery: jest.fn(() => false),
}));

import { Alert, Linking } from "react-native";

import { resolveClientGeoForQuery } from "@/features/chat/model/resolveClientGeoForQuery";
import { hasLocationPermission, requestDeviceGeo } from "@/lib/deviceLocation";
import { isGeoQuery } from "@/lib/places/localPlacesQuery";

const t = (key: string) => key;
const persistLocation = jest.fn().mockResolvedValue(undefined);

describe("resolveClientGeoForQuery", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSessionGeneration = 0;
    (Alert.alert as jest.Mock).mockReset();
    (isGeoQuery as jest.Mock).mockReturnValue(true);
    // The phone has not been asked yet: a geo ask shows the system sheet.
    (hasLocationPermission as jest.Mock).mockResolvedValue(false);
  });

  it("BUG FIX regression: shows the OS permission sheet even when the in-app toggle is off", async () => {
    (requestDeviceGeo as jest.Mock).mockResolvedValue({
      status: "granted",
      geo: { label: "Oakland, CA", latitude: 37.8, longitude: -122.27 },
    });

    const result = await resolveClientGeoForQuery(
      "tok",
      "Best coffee shops near me",
      t,
      persistLocation,
      false,
    );

    expect(requestDeviceGeo).toHaveBeenCalled();
    expect(Alert.alert).not.toHaveBeenCalled();
    expect(persistLocation).toHaveBeenCalledWith({
      location: "Oakland, CA",
      location_enabled: true,
    });
    expect(result).toEqual({
      ok: true,
      clientGeo: {
        label: "Oakland, CA",
        latitude: 37.8,
        longitude: -122.27,
      },
    });
  });

  it("returns fresh geo after the system permission grant", async () => {
    (requestDeviceGeo as jest.Mock).mockResolvedValue({
      status: "granted",
      geo: { label: "San Francisco, CA", latitude: 37.7, longitude: -122.4 },
    });

    const result = await resolveClientGeoForQuery(
      "tok",
      "Where am I right now",
      t,
      persistLocation,
      false,
    );

    expect(result).toEqual({
      ok: true,
      clientGeo: {
        label: "San Francisco, CA",
        latitude: 37.7,
        longitude: -122.4,
      },
    });
    expect(persistLocation).toHaveBeenCalledWith({
      location: "San Francisco, CA",
      location_enabled: true,
    });
    expect(Alert.alert).not.toHaveBeenCalled();
  });

  it("offers Open Settings only when permission is blocked", async () => {
    (requestDeviceGeo as jest.Mock).mockResolvedValue({ status: "blocked" });

    const result = await resolveClientGeoForQuery(
      "tok",
      "Where am I right now",
      t,
      persistLocation,
      false,
    );

    expect(result).toEqual({ ok: false });
    expect(Alert.alert).toHaveBeenCalledWith(
      "chat.location_required_title",
      "chat.location_required_body",
      expect.arrayContaining([
        expect.objectContaining({ text: "common.cancel" }),
        expect.objectContaining({ text: "chat.location_open_settings" }),
      ]),
    );
    const openSettingsAction = (Alert.alert as jest.Mock).mock.calls[0][2].find(
      (a: { text: string }) => a.text === "chat.location_open_settings",
    );
    openSettingsAction.onPress();
    await new Promise<void>((resolve) => setImmediate(resolve));
    expect(Linking.openSettings).toHaveBeenCalled();
  });

  it("does not alert when the user soft-denies the system sheet", async () => {
    (requestDeviceGeo as jest.Mock).mockResolvedValue({ status: "denied" });

    const result = await resolveClientGeoForQuery(
      "tok",
      "Where am I right now",
      t,
      persistLocation,
      false,
    );

    expect(result).toEqual({ ok: false });
    expect(Alert.alert).not.toHaveBeenCalled();
  });

  it("alerts in Expo Go instead of sending without a fix", async () => {
    (requestDeviceGeo as jest.Mock).mockResolvedValue({ status: "expo_go" });

    const result = await resolveClientGeoForQuery(
      "tok",
      "Best coffee shops near me",
      t,
      persistLocation,
      false,
    );

    expect(result).toEqual({ ok: false });
    expect(Alert.alert).toHaveBeenCalledWith(
      "chat.location_required_title",
      "settings.location_expo_go",
    );
    expect(persistLocation).not.toHaveBeenCalled();
  });

  it("reads quickly: a recent fix serves, and the waits are bounded", async () => {
    (requestDeviceGeo as jest.Mock).mockResolvedValue({ status: "no_fix" });
    await resolveClientGeoForQuery("tok", "Where am I right now", t, persistLocation, false);
    expect(requestDeviceGeo).toHaveBeenCalledWith({ quick: true });
  });

  it("sends the turn without a fix when none comes in time, saving nothing", async () => {
    (requestDeviceGeo as jest.Mock).mockResolvedValue({ status: "no_fix" });

    const result = await resolveClientGeoForQuery("tok", "Best coffee shops near me", t, persistLocation, false);

    expect(result).toEqual({ ok: true, clientGeo: null });
    expect(persistLocation).not.toHaveBeenCalled();
    expect(Alert.alert).not.toHaveBeenCalled();
  });

  it("waits on the profile save only as long as the caller's save does", async () => {
    (requestDeviceGeo as jest.Mock).mockResolvedValue({
      status: "granted",
      geo: { label: "Oakland, CA", latitude: 37.8, longitude: -122.27 },
    });
    (hasLocationPermission as jest.Mock).mockResolvedValue(true);
    // A save the caller does not wait for (location already on) returns nothing to await.
    const saveInBackground = jest.fn(() => undefined);
    const result = await resolveClientGeoForQuery("tok", "Best coffee shops near me", t, saveInBackground, true);
    // The switch is on already: only its place is kept fresh.
    expect(saveInBackground).toHaveBeenCalledWith({ location: "Oakland, CA" });
    expect(result).toMatchObject({ ok: true, clientGeo: { label: "Oakland, CA" } });
  });

  describe("the user's Location switch", () => {
    it("switched off in Data controls is never turned back on: the phone already allowing it, nothing is read, saved or sent", async () => {
      (hasLocationPermission as jest.Mock).mockResolvedValue(true);
      const result = await resolveClientGeoForQuery("tok", "Best coffee shops near me", t, persistLocation, false);
      // The turn goes without a place; the server's reply asks for one.
      expect(result).toEqual({ ok: true, clientGeo: null });
      expect(requestDeviceGeo).not.toHaveBeenCalled();
      expect(persistLocation).not.toHaveBeenCalled();
      expect(Alert.alert).not.toHaveBeenCalled();
    });

    it("before the server has said the switch, sends a fix with the turn and saves nothing", async () => {
      (hasLocationPermission as jest.Mock).mockResolvedValue(true);
      let named!: (label: string | null) => void;
      (requestDeviceGeo as jest.Mock).mockResolvedValue({
        status: "granted",
        geo: { label: null, latitude: 37.8, longitude: -122.27, lateLabel: new Promise((resolve) => { named = resolve; }) },
      });
      const result = await resolveClientGeoForQuery("tok", "Best coffee shops near me", t, persistLocation, null);
      expect(result).toMatchObject({ ok: true, clientGeo: { latitude: 37.8, longitude: -122.27 } });
      named("Oakland, CA");
      await new Promise<void>((resolve) => setImmediate(resolve));
      expect(persistLocation).not.toHaveBeenCalled();
    });

    it("before the server has said, the system sheet's Allow is the user's yes", async () => {
      (requestDeviceGeo as jest.Mock).mockResolvedValue({
        status: "granted",
        geo: { label: "Oakland, CA", latitude: 37.8, longitude: -122.27 },
      });
      await resolveClientGeoForQuery("tok", "Best coffee shops near me", t, persistLocation, null);
      expect(persistLocation).toHaveBeenCalledWith({ location: "Oakland, CA", location_enabled: true });
    });
  });

  describe("a place name slower than the turn", () => {
    function slowName() {
      let named!: (label: string | null) => void;
      const lateLabel = new Promise<string | null>((resolve) => { named = resolve; });
      (requestDeviceGeo as jest.Mock).mockResolvedValue({
        status: "granted",
        geo: { label: null, latitude: 37.8, longitude: -122.27, lateLabel },
      });
      return (label: string | null) => named(label);
    }

    it("sends the coordinates with the turn but never saves them as the profile's place", async () => {
      slowName();
      const result = await resolveClientGeoForQuery("tok", "Best coffee shops near me", t, persistLocation, false);
      expect(result).toEqual({
        ok: true,
        clientGeo: { label: "37.8000, -122.2700", latitude: 37.8, longitude: -122.27 },
      });
      expect(persistLocation).toHaveBeenCalledTimes(1);
      expect(persistLocation).toHaveBeenCalledWith({ location_enabled: true });
    });

    it("saves the name when the lookup finishes", async () => {
      const name = slowName();
      await resolveClientGeoForQuery("tok", "Best coffee shops near me", t, persistLocation, false);
      name("Oakland, CA, United States");
      await new Promise<void>((resolve) => setImmediate(resolve));
      expect(persistLocation).toHaveBeenLastCalledWith({ location: "Oakland, CA, United States" });
    });

    it.each([
      ["no name", () => null],
      ["another account", () => { mockSessionGeneration += 1; return "Oakland, CA"; }],
    ])("saves nothing more for %s", async (_case, outcome) => {
      const name = slowName();
      await resolveClientGeoForQuery("tok", "Best coffee shops near me", t, persistLocation, false);
      name(outcome());
      await new Promise<void>((resolve) => setImmediate(resolve));
      expect(persistLocation).toHaveBeenCalledTimes(1);
    });
  });
});
