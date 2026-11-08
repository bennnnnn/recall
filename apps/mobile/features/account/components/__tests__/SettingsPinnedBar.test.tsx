/**
 * Settings home's Back scrolled away with the profile, so a reader halfway down the page
 * had to scroll back up to leave (iOS Simulator pass, 2026-11-07). It now sits in a bar
 * outside the scrolling content.
 */
import type { ReactTestRendererJSON } from "react-test-renderer";
import { Animated, Text } from "react-native";
import { act, render } from "@testing-library/react-native";

import { SettingsPinnedBar } from "@/features/account/components/SettingsPinnedBar";
import { SettingsPage } from "@/features/account/components/settingsUi";

jest.mock("expo-router", () => ({
  Redirect: () => null,
  router: { push: jest.fn() },
  useRouter: () => ({ back: jest.fn(), canGoBack: () => true, replace: jest.fn() }),
}));
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ token: "token" }) }));

type Node = ReactTestRendererJSON;

function contains(node: Node | string, testID: string): boolean {
  if (typeof node === "string") return false;
  if (node.props.testID === testID) return true;
  return (node.children ?? []).some((child) => contains(child, testID));
}

function scrollView(node: Node | string): Node | null {
  if (typeof node === "string") return null;
  if (node.type === "RCTScrollView") return node;
  for (const child of node.children ?? []) {
    const found = scrollView(child);
    if (found) return found;
  }
  return null;
}

it("keeps Back outside the scrolling page, with the page's title in the bar", async () => {
  const ui = await render(
    <SettingsPage ownBarTitle="Settings">
      <Text>Profile</Text>
    </SettingsPage>,
  );
  const root = ui.toJSON() as Node;
  const scroll = scrollView(root);

  expect(scroll && contains(scroll, "stack-back")).toBe(false);
  expect(contains(root, "settings-pinned-bar")).toBe(true);
  expect(ui.getByTestId("stack-back")).toBeTruthy();
  expect(ui.getByText("Settings", { includeHiddenElements: true })).toBeTruthy();
});

it("draws no bar of its own on a page under a stack header", async () => {
  const ui = await render(
    <SettingsPage>
      <Text>Memory</Text>
    </SettingsPage>,
  );
  expect(ui.queryByTestId("settings-pinned-bar")).toBeNull();
  expect(ui.queryByTestId("stack-back")).toBeNull();
});

it("lets taps through while unseen, and holds them once drawn over the rows", async () => {
  const scrollY = new Animated.Value(0);
  const ui = await render(<SettingsPinnedBar title="Settings" scrollY={scrollY} />);
  const backdrop = () =>
    ui.getByTestId("settings-pinned-bar-backdrop", { includeHiddenElements: true });
  expect(backdrop().props.pointerEvents).toBe("none");
  expect(ui.getByText("Settings", { includeHiddenElements: true }).props.pointerEvents).toBe("none");

  await act(async () => scrollY.setValue(200));
  expect(backdrop().props.pointerEvents).toBe("auto");

  await act(async () => scrollY.setValue(0));
  expect(backdrop().props.pointerEvents).toBe("none");
});
