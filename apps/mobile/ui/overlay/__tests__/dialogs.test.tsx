import { act, fireEvent, render, waitFor } from "@testing-library/react-native";
import { Alert, Linking } from "react-native";

import { DialogHost } from "../DialogHost";
import { alertDialog, confirmDialog, offerSettings, type SettingsPermission } from "../dialogs";
import en from "@/lib/i18n/en.json";
import { lightTheme as mockLightTheme } from "@/lib/theme";

jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));

describe("confirmDialog() without a host", () => {
  it("falls back to the platform alert with the same choices", async () => {
    const spy = jest.spyOn(Alert, "alert").mockImplementation(() => undefined);
    const answer = confirmDialog({
      title: "Delete chat?",
      message: "This can't be undone.",
      confirmLabel: "Delete",
      cancelLabel: "Cancel",
      destructive: true,
    });
    const [, , buttons] = spy.mock.calls[0];
    expect(buttons?.map((b) => [b.text, b.style])).toEqual([
      ["Cancel", "cancel"],
      ["Delete", "destructive"],
    ]);
    buttons?.[1].onPress?.();
    await expect(answer).resolves.toBe(true);
    spy.mockRestore();
  });
});

describe("DialogHost", () => {
  it("shows confirmDialog() as a themed dialog and resolves with the choice", async () => {
    const view = await render(<DialogHost />);
    let answer!: Promise<boolean>;
    await act(async () => {
      answer = confirmDialog({ title: "Sign out?", confirmLabel: "Sign out", cancelLabel: "Cancel" });
    });
    expect(view.getByText("Sign out?")).toBeTruthy();
    await fireEvent.press(view.getByRole("button", { name: "Sign out" }));
    await expect(answer).resolves.toBe(true);
  });

  it("resolves false on Cancel and on a scrim tap", async () => {
    const view = await render(<DialogHost />);
    let first!: Promise<boolean>;
    await act(async () => {
      first = confirmDialog({ title: "Archive all?", confirmLabel: "Archive", cancelLabel: "Cancel" });
    });
    await fireEvent.press(view.getByRole("button", { name: "Cancel" }));
    await expect(first).resolves.toBe(false);

    await waitFor(() => expect(view.queryByText("Archive all?")).toBeNull());
    let second!: Promise<boolean>;
    await act(async () => {
      second = confirmDialog({ title: "Revoke?", confirmLabel: "Revoke", cancelLabel: "Cancel" });
    });
    await waitFor(() => expect(view.getByText("Revoke?")).toBeTruthy());
    await fireEvent.press(view.getByTestId("overlay-scrim", { includeHiddenElements: true }));
    await expect(second).resolves.toBe(false);
  });

  it("shows queued dialogs one after another", async () => {
    const view = await render(<DialogHost />);
    let first!: Promise<void>;
    let second!: Promise<void>;
    await act(async () => {
      first = alertDialog({ title: "First" });
      second = alertDialog({ title: "Second" });
    });
    expect(view.getByText("First")).toBeTruthy();
    expect(view.queryByText("Second")).toBeNull();
    await fireEvent.press(view.getByRole("button", { name: "common.ok" }));
    await first;
    await waitFor(() => expect(view.getByText("Second")).toBeTruthy());
    await fireEvent.press(view.getByRole("button", { name: "common.ok" }));
    await second;
  });
});

// Six copies of this dialog had their own words and cancel labels (Cancel, Not now), named
// the camera, microphone and photos with the location key, and one left for Settings unasked.
describe("offerSettings()", () => {
  const permissions: SettingsPermission[] = ["camera", "microphone", "photos", "location", "notifications"];
  let alert: jest.SpyInstance;
  let open: jest.SpyInstance;
  beforeEach(() => {
    alert = jest.spyOn(Alert, "alert").mockImplementation(() => undefined);
    open = jest.spyOn(Linking, "openSettings").mockResolvedValue(undefined);
  });
  afterEach(() => {
    alert.mockRestore();
    open.mockRestore();
  });
  const buttons = () => alert.mock.calls.at(-1)?.[2] as { text: string; onPress?: () => void }[];
  const strings = en as Record<string, string>;

  it.each(permissions)("asks for %s in its own words, with Not now and Open Settings", async (permission) => {
    const answer = offerSettings(permission);
    expect(alert).toHaveBeenLastCalledWith(
      `permissions.${permission}_title`,
      `permissions.${permission}_body`,
      expect.any(Array),
    );
    expect(buttons().map((button) => button.text)).toEqual(["common.not_now", "common.open_settings"]);
    expect([strings[`permissions.${permission}_title`], strings[`permissions.${permission}_body`]]).toEqual([
      expect.any(String),
      expect.any(String),
    ]);
    expect(open).not.toHaveBeenCalled();
    buttons()[1]?.onPress?.();
    await expect(answer).resolves.toBe(true);
    expect(open).toHaveBeenCalledTimes(1);
  });

  it("stays in the app on Not now", async () => {
    const answer = offerSettings("camera");
    buttons()[0]?.onPress?.();
    await expect(answer).resolves.toBe(false);
    expect(open).not.toHaveBeenCalled();
  });

  it("says so when Settings cannot open", async () => {
    open.mockRejectedValueOnce(new Error("no settings"));
    const warn = jest.spyOn(console, "warn").mockImplementation(() => undefined);
    const answer = offerSettings("photos");
    buttons()[1]?.onPress?.();
    await expect(answer).resolves.toBe(false);
    expect(alert).toHaveBeenLastCalledWith("common.open_settings_failed");
    warn.mockRestore();
  });
});
