import { fireEvent, render } from "@testing-library/react-native";
import { Platform } from "react-native";

import { menuItemRole } from "../../controls/a11yRoles";
import { Menu, type MenuEntry } from "../Menu";
import { lightTheme as mockLightTheme } from "@/lib/theme";

jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 47, bottom: 34, left: 0, right: 0 }),
}));

function items(onShare = jest.fn(), onDelete = jest.fn()): MenuEntry[] {
  return [
    { key: "share", label: "Share", icon: "share", onPress: onShare },
    { key: "pin", label: "Pin", icon: "pin", onPress: jest.fn() },
    "separator",
    { key: "delete", label: "Delete", icon: "trash", onPress: onDelete, destructive: true },
  ];
}

describe("Menu", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("shows the title and one row per item", async () => {
    const view = await render(
      <Menu visible onClose={jest.fn()} items={items()} title="Learn Spanish" />,
    );
    expect(view.getByText("Learn Spanish")).toBeTruthy();
    expect(view.getByRole(menuItemRole(), { name: "Share" })).toBeTruthy();
    expect(view.getByRole(menuItemRole(), { name: "Delete" })).toBeTruthy();
  });

  it("closes first, then runs the row, so the row can open another sheet", async () => {
    const order: string[] = [];
    const onClose = jest.fn(() => order.push("close"));
    const onShare = jest.fn(() => order.push("share"));
    const view = await render(<Menu visible onClose={onClose} items={items(onShare)} />);
    await fireEvent.press(view.getByRole(menuItemRole(), { name: "Share" }));
    expect(order).toEqual(["close", "share"]);
  });

  it("draws destructive rows in the danger ink", async () => {
    const view = await render(<Menu visible onClose={jest.fn()} items={items()} />);
    const label = view.getByText("Delete");
    expect(label.props.style).toEqual(
      expect.arrayContaining([expect.objectContaining({ color: mockLightTheme.danger })]),
    );
  });

  it("marks the current choice in a selectable menu", async () => {
    const view = await render(
      <Menu
        visible
        selectable
        onClose={jest.fn()}
        items={[
          { key: "light", label: "Light", onPress: jest.fn() },
          { key: "dark", label: "Dark", onPress: jest.fn(), selected: true },
        ]}
      />,
    );
    expect(view.getByRole("radio", { name: "Dark" }).props.accessibilityState.checked).toBe(true);
    expect(view.getByRole("radio", { name: "Light" }).props.accessibilityState.checked).toBe(false);
  });

  // React Native gives VoiceOver nothing for `menuitem` (no trait, no value): a row read as bare
  // text, with no "button" (iPhone 17 Pro Max Simulator, 2026-11-08).
  it("reads an action as a button on iOS and as a menu item on Android", async () => {
    const ios = await render(<Menu visible onClose={jest.fn()} items={items()} />);
    expect(ios.getByRole("button", { name: "Share" })).toBeTruthy();
    expect(ios.queryByRole("menuitem")).toBeNull();
    await ios.unmount();

    jest.replaceProperty(Platform, "OS", "android");
    const android = await render(<Menu visible onClose={jest.fn()} items={items()} />);
    expect(android.getByRole("menuitem", { name: "Share" })).toBeTruthy();
  });

  // The To-do list's ⋯: Select is an action; its views are choices with the current one ticked.
  it("reads a row that carries a check as a choice, beside the actions", async () => {
    const view = await render(
      <Menu
        visible
        onClose={jest.fn()}
        items={[
          { key: "select", label: "Select", onPress: jest.fn() },
          "separator",
          { key: "today", label: "Today", onPress: jest.fn(), selected: true },
          { key: "all", label: "All", onPress: jest.fn(), selected: false },
        ]}
      />,
    );
    expect(view.getByRole(menuItemRole(), { name: "Select" }).props.accessibilityState).toEqual({ disabled: false });
    expect(view.getByRole("radio", { name: "Today" }).props.accessibilityState).toEqual({ disabled: false, checked: true });
    expect(view.getByRole("radio", { name: "All" }).props.accessibilityState).toEqual({ disabled: false, checked: false });
  });

  it("ignores disabled rows", async () => {
    const onPress = jest.fn();
    const view = await render(
      <Menu
        visible
        onClose={jest.fn()}
        items={[{ key: "x", label: "Pro only", onPress, disabled: true }]}
      />,
    );
    await fireEvent.press(view.getByRole(menuItemRole(), { name: "Pro only" }));
    expect(onPress).not.toHaveBeenCalled();
  });

  it("renders nothing while closed", async () => {
    const view = await render(<Menu visible={false} onClose={jest.fn()} items={items()} />);
    expect(view.queryByText("Share")).toBeNull();
  });

  it("closes from the scrim", async () => {
    const onClose = jest.fn();
    const view = await render(
      <Menu visible onClose={onClose} items={items()} testID="menu" />,
    );
    // The card is the accessibility modal, so its sibling scrim is hidden
    // from screen readers (they close with the escape gesture instead).
    await fireEvent.press(view.getByTestId("menu-scrim", { includeHiddenElements: true }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
