import { act, fireEvent, render, waitFor } from "@testing-library/react-native";
import { Alert } from "react-native";

import { DialogHost } from "../DialogHost";
import { alert, confirm } from "../dialogs";
import { lightTheme as mockLightTheme } from "@/lib/theme";

jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));

describe("confirm() without a host", () => {
  it("falls back to the platform alert with the same choices", async () => {
    const spy = jest.spyOn(Alert, "alert").mockImplementation(() => undefined);
    const answer = confirm({
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
  it("shows confirm() as a themed dialog and resolves with the choice", async () => {
    const view = await render(<DialogHost />);
    let answer!: Promise<boolean>;
    await act(async () => {
      answer = confirm({ title: "Sign out?", confirmLabel: "Sign out", cancelLabel: "Cancel" });
    });
    expect(view.getByText("Sign out?")).toBeTruthy();
    fireEvent.press(view.getByRole("button", { name: "Sign out" }));
    await expect(answer).resolves.toBe(true);
  });

  it("resolves false on Cancel and on a scrim tap", async () => {
    const view = await render(<DialogHost />);
    let first!: Promise<boolean>;
    await act(async () => {
      first = confirm({ title: "Archive all?", confirmLabel: "Archive", cancelLabel: "Cancel" });
    });
    fireEvent.press(view.getByRole("button", { name: "Cancel" }));
    await expect(first).resolves.toBe(false);

    await waitFor(() => expect(view.queryByText("Archive all?")).toBeNull());
    let second!: Promise<boolean>;
    await act(async () => {
      second = confirm({ title: "Revoke?", confirmLabel: "Revoke", cancelLabel: "Cancel" });
    });
    await waitFor(() => expect(view.getByText("Revoke?")).toBeTruthy());
    fireEvent.press(view.getByTestId("overlay-scrim", { includeHiddenElements: true }));
    await expect(second).resolves.toBe(false);
  });

  it("shows queued dialogs one after another", async () => {
    const view = await render(<DialogHost />);
    let first!: Promise<void>;
    let second!: Promise<void>;
    await act(async () => {
      first = alert({ title: "First" });
      second = alert({ title: "Second" });
    });
    expect(view.getByText("First")).toBeTruthy();
    expect(view.queryByText("Second")).toBeNull();
    fireEvent.press(view.getByRole("button", { name: "common.ok" }));
    await first;
    await waitFor(() => expect(view.getByText("Second")).toBeTruthy());
    fireEvent.press(view.getByRole("button", { name: "common.ok" }));
    await second;
  });
});
