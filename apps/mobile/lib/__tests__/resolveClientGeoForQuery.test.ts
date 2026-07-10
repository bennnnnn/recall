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
const mergeUser = jest.fn();

describe("resolveClientGeoForQuery", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (isGeoQuery as jest.Mock).mockReturnValue(true);
  });

  it("returns fresh geo after the system permission grant", async () => {
    (requestDeviceGeo as jest.Mock).mockResolvedValue({
      status: "granted",
      geo: { label: "San Francisco, CA", latitude: 37.7, longitude: -122.4 },
    });

    const result = await resolveClientGeoForQuery("tok", "Where am I right now", t, mergeUser);

    expect(result).toEqual({
      ok: true,
      clientGeo: {
        label: "San Francisco, CA",
        latitude: 37.7,
        longitude: -122.4,
      },
    });
    expect(mergeUser).toHaveBeenCalledWith({
      location: "San Francisco, CA",
      location_enabled: true,
    });
    expect(Alert.alert).not.toHaveBeenCalled();
  });

  it("offers Open Settings only when permission is blocked", async () => {
    (requestDeviceGeo as jest.Mock).mockResolvedValue({ status: "blocked" });

    const result = await resolveClientGeoForQuery("tok", "Where am I right now", t, mergeUser);

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

    const result = await resolveClientGeoForQuery("tok", "Where am I right now", t, mergeUser);

    expect(result).toEqual({ ok: false });
    expect(Alert.alert).not.toHaveBeenCalled();
  });
});
