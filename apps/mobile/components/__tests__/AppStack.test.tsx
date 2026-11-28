// The root stack under the real Expo Router: a sign-out takes the account's screens out of
// the history, and a sign-in starts on one chat screen (pre-launch review, 2026-11-27: each
// screen's own Redirect left the old chat under the sign-in, and each sign-in stacked
// another chat screen on it).
import "./support/expoGlobal";

import { useEffect } from "react";
import { Text } from "react-native";
import { type Href, router } from "expo-router";
import { act, renderRouter, screen } from "expo-router/testing-library";

import { AppStack } from "@/components/AppStack";

// What the router reads from `expo`: no splash screen, native views or Liquid Glass here.
jest.mock("expo", () => ({
  requireOptionalNativeModule: () => null,
  requireNativeModule: () => ({ isLiquidGlassAvailable: false }),
  Platform: { OS: "ios" },
  requireNativeView: () => () => null,
  registerRootComponent: jest.fn(),
}));
// An ES module the router imports for one constructor; Jest here loads CommonJS.
jest.mock("standard-navigation", () => ({
  createStandardNavigator: (NavigatorContent: unknown) => ({
    type: "standard",
    version: 1,
    NavigatorContent,
  }),
}));

let signedIn = true;
let setSignedIn: (value: boolean) => void = () => {};
let chatMounts = 0;

function RootLayout() {
  const React = jest.requireActual<typeof import("react")>("react");
  const [value, setValue] = React.useState(signedIn);
  setSignedIn = (next) => {
    signedIn = next;
    setValue(next);
  };
  return <AppStack signedIn={value} />;
}

function ChatScreen() {
  useEffect(() => {
    chatMounts += 1;
  }, []);
  return <Text>chat screen</Text>;
}

const routes = {
  _layout: RootLayout,
  index: ChatScreen,
  login: () => <Text>login screen</Text>,
  onboarding: () => <Text>onboarding screen</Text>,
  consent: () => <Text>consent screen</Text>,
  todos: () => <Text>todos screen</Text>,
  gallery: () => <Text>library screen</Text>,
  "settings/_layout": () => null,
  "memory/_layout": () => null,
};

const shown = (text: string) => screen.queryByText(text, { includeHiddenElements: true });

beforeEach(() => {
  signedIn = true;
  chatMounts = 0;
});

it("takes the account's screens out of the history on sign-out: Back shows no old chat", async () => {
  await renderRouter(routes as Parameters<typeof renderRouter>[0], { initialUrl: "/" });
  await act(async () => router.push("/todos" as Href));
  expect(screen.getByText("todos screen")).toBeTruthy();

  await act(async () => setSignedIn(false));

  expect(screen.getByText("login screen")).toBeTruthy();
  expect(shown("chat screen")).toBeNull();
  expect(shown("todos screen")).toBeNull();
  expect(router.canGoBack()).toBe(false);
});

it("starts a sign-in on one chat screen, however many times the account signs in", async () => {
  await renderRouter(routes as Parameters<typeof renderRouter>[0], { initialUrl: "/" });
  for (let round = 0; round < 3; round += 1) {
    await act(async () => setSignedIn(false));
    expect(screen.getByText("login screen")).toBeTruthy();
    await act(async () => setSignedIn(true));
    expect(screen.getByText("chat screen")).toBeTruthy();
  }
  expect(screen.queryAllByText("chat screen", { includeHiddenElements: true })).toHaveLength(1);
  expect(shown("login screen")).toBeNull();
  expect(router.canGoBack()).toBe(false);
});
