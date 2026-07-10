jest.mock("react-native", () => ({
  Alert: { alert: jest.fn() },
  Linking: { openSettings: jest.fn() },
}));

jest.mock("@/lib/deviceLocation", () => ({
  requestDeviceGeo: jest.fn(),
}));

jest.mock("@/lib/localPlacesQuery", () => ({
  isGeoQuery: jest.fn(),
  isAmbiguousLocalPlacesQuery: jest.fn(() => false),
}));

import { Alert, Linking } from "react-native";

import { resolveClientGeoForQuery } from "@/lib/resolveClientGeoForQuery";
import { requestDeviceGeo } from "@/lib/deviceLocation";
import { isGeoQuery } from "@/lib/localPlacesQuery";

const t = (key: string) => key;
const persistLocation = jest.fn().mockResolvedValue(undefined);

describe("resolveClientGeoForQuery", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (Alert.alert as jest.Mock).mockReset();
    (isGeoQuery as jest.Mock).mockReturnValue(true);
  });

  it("offers Turn on when the in-app Location toggle is off, then continues", async () => {
    (Alert.alert as jest.Mock).mockImplementation((_title, _body, buttons) => {
      const turnOn = buttons.find((b: { text: string }) => b.text === "chat.location_turn_on");
      turnOn.onPress();
    });
    (requestDeviceGeo as jest.Mock).mockResolvedValue({
      status: "granted",
      geo: { label: "Oakland, CA", latitude: 37.8, longitude: -122.27 },
    });

    const result = await resolveClientGeoForQuery(
      "tok",
      "Where am I right now",
      t,
      persistLocation,
      false,
    );

    expect(Alert.alert).toHaveBeenCalledWith(
      "chat.location_required_title",
      "chat.location_disabled_body",
      expect.arrayContaining([
        expect.objectContaining({ text: "common.cancel" }),
        expect.objectContaining({ text: "chat.location_turn_on" }),
      ]),
    );
    expect(requestDeviceGeo).toHaveBeenCalled();
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

  it("cancels when the user declines Turn on", async () => {
    (Alert.alert as jest.Mock).mockImplementation((_title, _body, buttons) => {
      const cancel = buttons.find((b: { text: string }) => b.text === "common.cancel");
      cancel.onPress();
    });

    const result = await resolveClientGeoForQuery(
      "tok",
      "Where am I right now",
      t,
      persistLocation,
      false,
    );

    expect(result).toEqual({ ok: false });
    expect(requestDeviceGeo).not.toHaveBeenCalled();
    expect(persistLocation).not.toHaveBeenCalled();
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
      true,
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
      true,
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
    expect(Linking.openSettings).toHaveBeenCalled();
  });

  it("does not alert when the user soft-denies the system sheet", async () => {
    (requestDeviceGeo as jest.Mock).mockResolvedValue({ status: "denied" });

    const result = await resolveClientGeoForQuery(
      "tok",
      "Where am I right now",
      t,
      persistLocation,
      true,
    );

    expect(result).toEqual({ ok: false });
    expect(Alert.alert).not.toHaveBeenCalled();
  });
});
