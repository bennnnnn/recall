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

jest.mock("@/lib/syncRecords", () => ({
  recentSyncAt: jest.fn(async () => null),
  recordSync: jest.fn(async () => undefined),
}));

import { Alert, Linking } from "react-native";

import { locationSwitchOf, resolveClientGeoForQuery } from "@/features/chat/model/resolveClientGeoForQuery";
import { hasLocationPermission, requestDeviceGeo } from "@/lib/deviceLocation";
import { isGeoQuery } from "@/lib/places/localPlacesQuery";
import { recentSyncAt, recordSync } from "@/lib/syncRecords";

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
    (recentSyncAt as jest.Mock).mockResolvedValue(null);
  });

  it("BUG FIX regression: shows the OS permission sheet for a switch never chosen (#1058)", async () => {
    (requestDeviceGeo as jest.Mock).mockResolvedValue({
      status: "granted",
      geo: { label: "Oakland, CA", latitude: 37.8, longitude: -122.27 },
    });

    const result = await resolveClientGeoForQuery(
      "tok",
      "Best coffee shops near me",
      t,
      persistLocation,
      "never_chosen",
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
      "never_chosen",
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
      "never_chosen",
    );

    expect(result).toEqual({ ok: false });
    expect(Alert.alert).toHaveBeenCalledWith(
      "permissions.location_title",
      "permissions.location_body",
      expect.arrayContaining([
        expect.objectContaining({ text: "common.not_now" }),
        expect.objectContaining({ text: "common.open_settings" }),
      ]),
    );
    const openSettingsAction = (Alert.alert as jest.Mock).mock.calls[0][2].find(
      (a: { text: string }) => a.text === "common.open_settings",
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
      "never_chosen",
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
      "never_chosen",
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
    await resolveClientGeoForQuery("tok", "Where am I right now", t, persistLocation, "never_chosen");
    expect(requestDeviceGeo).toHaveBeenCalledWith({ quick: true });
  });

  it("sends the turn without a fix when none comes in time, saving nothing", async () => {
    (requestDeviceGeo as jest.Mock).mockResolvedValue({ status: "no_fix" });

    const result = await resolveClientGeoForQuery("tok", "Best coffee shops near me", t, persistLocation, "never_chosen");

    expect(result).toEqual({ ok: true, clientGeo: null });
    expect(persistLocation).not.toHaveBeenCalled();
    expect(Alert.alert).not.toHaveBeenCalled();
  });

  it.each([
    // The switch is on already: the turn goes while its place saves.
    ["on", { location: "Oakland, CA" }, true],
    // The server reads a fix only from a user whose Location is on: that save comes first.
    ["never_chosen", { location: "Oakland, CA", location_enabled: true }, false],
  ] as const)("with the switch %p, the turn waits for the profile save: %p", async (locationSwitch, patch, goesFirst) => {
    (requestDeviceGeo as jest.Mock).mockResolvedValue({
      status: "granted",
      geo: { label: "Oakland, CA", latitude: 37.8, longitude: -122.27 },
    });
    let saved!: () => void;
    const save = jest.fn(() => new Promise<void>((resolve) => { saved = resolve; }));
    let done = false;
    const resolving = resolveClientGeoForQuery("tok", "Best coffee shops near me", t, save, locationSwitch).then((result) => {
      done = true;
      return result;
    });
    await new Promise<void>((resolve) => setImmediate(resolve));
    expect(save).toHaveBeenCalledWith(patch);
    expect(done).toBe(goesFirst);
    saved();
    await expect(resolving).resolves.toMatchObject({ ok: true, clientGeo: { label: "Oakland, CA" } });
  });

  describe("the user's Location switch", () => {
    const oakland = { status: "granted", geo: { label: "Oakland, CA", latitude: 37.8, longitude: -122.27 } };

    it("switched off in Data controls is never turned back on: nothing is read, saved or sent", async () => {
      (hasLocationPermission as jest.Mock).mockResolvedValue(true);
      const result = await resolveClientGeoForQuery("tok", "Best coffee shops near me", t, persistLocation, "off");
      // The turn goes without a place; the server's reply asks for one.
      expect(result).toEqual({ ok: true, clientGeo: null });
      expect(requestDeviceGeo).not.toHaveBeenCalled();
      expect(persistLocation).not.toHaveBeenCalled();
      expect(Alert.alert).not.toHaveBeenCalled();
    });

    it.each([
      // A second account on a phone the first already allowed, or iOS allowed later in Settings.
      ["the phone already allows location", true],
      ["the system sheet asks", false],
    ])("never chosen, a fix is used and turns it on when %s", async (_case, allowed) => {
      (hasLocationPermission as jest.Mock).mockResolvedValue(allowed);
      (requestDeviceGeo as jest.Mock).mockResolvedValue(oakland);
      const result = await resolveClientGeoForQuery("tok", "Best coffee shops near me", t, persistLocation, "never_chosen");
      expect(result).toMatchObject({ ok: true, clientGeo: { label: "Oakland, CA" } });
      expect(persistLocation).toHaveBeenCalledWith({ location: "Oakland, CA", location_enabled: true });
    });

    it("never chosen after a save that failed, the next ask saves again", async () => {
      (requestDeviceGeo as jest.Mock).mockResolvedValue(oakland);
      persistLocation.mockRejectedValueOnce(new Error("offline"));
      await expect(
        resolveClientGeoForQuery("tok", "Best coffee shops near me", t, persistLocation, "never_chosen"),
      ).resolves.toMatchObject({ ok: true });
      // The server still has it never chosen: the next question asks the same way.
      await resolveClientGeoForQuery("tok", "Best coffee shops near me", t, persistLocation, "never_chosen");
      expect(persistLocation).toHaveBeenCalledTimes(2);
      expect(persistLocation).toHaveBeenLastCalledWith({ location: "Oakland, CA", location_enabled: true });
    });

    it("before the server has said the switch, sends a fix with the turn and saves nothing", async () => {
      (hasLocationPermission as jest.Mock).mockResolvedValue(true);
      let named!: (label: string | null) => void;
      (requestDeviceGeo as jest.Mock).mockResolvedValue({
        status: "granted",
        geo: { label: null, latitude: 37.8, longitude: -122.27, lateLabel: new Promise((resolve) => { named = resolve; }) },
      });
      const result = await resolveClientGeoForQuery("tok", "Best coffee shops near me", t, persistLocation, "unknown");
      expect(result).toMatchObject({ ok: true, clientGeo: { latitude: 37.8, longitude: -122.27 } });
      named("Oakland, CA");
      await new Promise<void>((resolve) => setImmediate(resolve));
      expect(persistLocation).not.toHaveBeenCalled();
    });

    it("before the server has said, the system sheet's Allow is the user's yes", async () => {
      (requestDeviceGeo as jest.Mock).mockResolvedValue(oakland);
      await resolveClientGeoForQuery("tok", "Best coffee shops near me", t, persistLocation, "unknown");
      expect(persistLocation).toHaveBeenCalledWith({ location: "Oakland, CA", location_enabled: true });
    });

    it.each([
      [true, true, "on"],
      [false, true, "off"],
      [null, true, "never_chosen"],
      [undefined, true, "never_chosen"],
      [true, false, "unknown"],
    ])("reads the server's %p (confirmed %p) as %p", (enabled, confirmed, expected) => {
      expect(locationSwitchOf(enabled, confirmed)).toBe(expected);
    });
  });

  describe("the place the account saved", () => {
    // An access token for account "acct-1": the record of its saved place is per account.
    const token = `h.${btoa(JSON.stringify({ sub: "acct-1" }))}.s`;
    const oakland = { status: "granted", geo: { label: "Oakland, CA", latitude: 37.8, longitude: -122.27 } };

    it("answers while a fix saved it in the last fifteen minutes: nothing is read, saved or sent", async () => {
      // A places question with Location on read GPS, reverse-geocoded and saved the
      // profile every time (2026-11-08); the server reads the saved place instead.
      (recentSyncAt as jest.Mock).mockResolvedValue(Date.now() - 60_000);
      (hasLocationPermission as jest.Mock).mockResolvedValue(true);
      const result = await resolveClientGeoForQuery(token, "What's the best restaurant near me?", t, persistLocation, "on");
      expect(result).toEqual({ ok: true, clientGeo: null });
      expect(recentSyncAt).toHaveBeenCalledWith("location", "acct-1", 15 * 60_000);
      expect(requestDeviceGeo).not.toHaveBeenCalled();
      expect(persistLocation).not.toHaveBeenCalled();
    });

    it("older, the phone reads and saves its place again, and notes when", async () => {
      (requestDeviceGeo as jest.Mock).mockResolvedValue(oakland);
      const result = await resolveClientGeoForQuery(token, "coffee near me", t, persistLocation, "on");
      expect(result).toMatchObject({ ok: true, clientGeo: { label: "Oakland, CA" } });
      expect(persistLocation).toHaveBeenCalledWith({ location: "Oakland, CA" });
      expect(recordSync).toHaveBeenCalledWith("location", "acct-1");
    });

    it.each(["never_chosen", "unknown"] as const)(
      "with the switch %p, a recent record still asks the phone (the system sheet, #1058)",
      async (locationSwitch) => {
        (recentSyncAt as jest.Mock).mockResolvedValue(Date.now() - 60_000);
        (requestDeviceGeo as jest.Mock).mockResolvedValue(oakland);
        await resolveClientGeoForQuery(token, "coffee near me", t, persistLocation, locationSwitch);
        expect(requestDeviceGeo).toHaveBeenCalledWith({ quick: true });
      },
    );

    it("notes nothing when the fix saved no place", async () => {
      (hasLocationPermission as jest.Mock).mockResolvedValue(true);
      (requestDeviceGeo as jest.Mock).mockResolvedValue(oakland);
      await resolveClientGeoForQuery(token, "coffee near me", t, persistLocation, "unknown");
      expect(persistLocation).not.toHaveBeenCalled();
      expect(recordSync).not.toHaveBeenCalled();
    });

    it("a save that fails in the background neither fails the turn nor counts the place as recent", async () => {
      // A failed profile save still marked the place fresh, so the next questions read a
      // place the server never got (review, 2026-11-09).
      (requestDeviceGeo as jest.Mock).mockResolvedValue(oakland);
      const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
      const failing = jest.fn(() => Promise.reject(new Error("offline")));
      const result = await resolveClientGeoForQuery(token, "coffee near me", t, failing, "on");
      await new Promise<void>((resolve) => setImmediate(resolve));
      expect(result).toMatchObject({ ok: true, clientGeo: { label: "Oakland, CA" } });
      expect(recordSync).not.toHaveBeenCalled();
      warn.mockRestore();
    });

    it("counts the place as recent only once its save lands", async () => {
      (requestDeviceGeo as jest.Mock).mockResolvedValue(oakland);
      let saved!: () => void;
      const save = jest.fn(() => new Promise<void>((resolve) => { saved = resolve; }));
      await resolveClientGeoForQuery(token, "coffee near me", t, save, "on");
      expect(recordSync).not.toHaveBeenCalled();
      saved();
      await new Promise<void>((resolve) => setImmediate(resolve));
      expect(recordSync).toHaveBeenCalledWith("location", "acct-1");
    });

    it("with Location turned off in iOS Settings, a recent place is not used: the phone is asked", async () => {
      // The saved place answered for fifteen minutes after the phone stopped letting
      // Recall read it (review, 2026-11-09).
      (recentSyncAt as jest.Mock).mockResolvedValue(Date.now() - 60_000);
      (hasLocationPermission as jest.Mock).mockResolvedValue(false);
      (requestDeviceGeo as jest.Mock).mockResolvedValue({ status: "blocked" });
      const result = await resolveClientGeoForQuery(token, "What's the weather tomorrow?", t, persistLocation, "on");
      expect(requestDeviceGeo).toHaveBeenCalled();
      expect(result).toEqual({ ok: false });
    });

    it("notes a place name that came after the turn once it is saved", async () => {
      let named!: (label: string | null) => void;
      (requestDeviceGeo as jest.Mock).mockResolvedValue({
        status: "granted",
        geo: { label: null, latitude: 37.8, longitude: -122.27, lateLabel: new Promise((resolve) => { named = resolve; }) },
      });
      await resolveClientGeoForQuery(token, "coffee near me", t, persistLocation, "on");
      expect(recordSync).not.toHaveBeenCalled();
      named("Oakland, CA");
      await new Promise<void>((resolve) => setImmediate(resolve));
      expect(persistLocation).toHaveBeenCalledWith({ location: "Oakland, CA" });
      expect(recordSync).toHaveBeenCalledWith("location", "acct-1");
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
      const result = await resolveClientGeoForQuery("tok", "Best coffee shops near me", t, persistLocation, "never_chosen");
      expect(result).toEqual({
        ok: true,
        clientGeo: { label: "37.8000, -122.2700", latitude: 37.8, longitude: -122.27 },
      });
      expect(persistLocation).toHaveBeenCalledTimes(1);
      expect(persistLocation).toHaveBeenCalledWith({ location_enabled: true });
    });

    it("saves the name when the lookup finishes", async () => {
      const name = slowName();
      await resolveClientGeoForQuery("tok", "Best coffee shops near me", t, persistLocation, "never_chosen");
      name("Oakland, CA, United States");
      await new Promise<void>((resolve) => setImmediate(resolve));
      expect(persistLocation).toHaveBeenLastCalledWith({ location: "Oakland, CA, United States" });
    });

    it.each([
      ["no name", () => null],
      ["another account", () => { mockSessionGeneration += 1; return "Oakland, CA"; }],
    ])("saves nothing more for %s", async (_case, outcome) => {
      const name = slowName();
      await resolveClientGeoForQuery("tok", "Best coffee shops near me", t, persistLocation, "never_chosen");
      name(outcome());
      await new Promise<void>((resolve) => setImmediate(resolve));
      expect(persistLocation).toHaveBeenCalledTimes(1);
    });
  });
});
