// A screen that throws while it renders shows the shared error view in its
// place, under the real Expo Router: the chat under it stays mounted, Try
// again draws the screen afresh, and the crash is reported once.
import "./support/expoGlobal";

import { Text } from "react-native";
import { ErrorBoundary as RouterErrorBoundary, Stack, router } from "expo-router";
import { act, fireEvent, renderRouter, screen } from "expo-router/testing-library";

import { ScreenErrorBoundary } from "@/components/ScreenErrorBoundary";
import { reportBoundaryError } from "@/lib/sentry";

jest.mock("@/lib/sentry", () => ({ reportBoundaryError: jest.fn() }));
// What the router reads from `expo`: no splash screen and no native views here.
jest.mock("expo", () => ({
  requireOptionalNativeModule: () => null,
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

/** While true, the page throws each time it renders. */
let failing = false;

function ProfilePage() {
  if (failing) throw new Error("profile render failed");
  return <Text>profile page</Text>;
}

/** The app's shape: a root stack whose layout keeps the router's last-resort boundary. */
function routes(pageBoundary: typeof ScreenErrorBoundary | undefined) {
  return {
    _layout: { default: () => <Stack />, ErrorBoundary: RouterErrorBoundary },
    index: () => <Text>chat screen</Text>,
    "settings/_layout": () => <Stack />,
    "settings/profile": pageBoundary
      ? { default: ProfilePage, ErrorBoundary: pageBoundary }
      : ProfilePage,
    "memory/[key]": { default: ProfilePage, ErrorBoundary: ScreenErrorBoundary },
  };
}

async function openProfileThatThrows(pageBoundary?: typeof ScreenErrorBoundary) {
  await renderRouter(routes(pageBoundary), { initialUrl: "/" });
  expect(screen.getByText("chat screen")).toBeTruthy();
  failing = true;
  await act(async () => router.push("/settings/profile"));
}

describe("a screen that throws while it renders", () => {
  const error = jest.spyOn(console, "error").mockImplementation(() => undefined);
  const warn = jest.spyOn(console, "warn").mockImplementation(() => undefined);

  beforeEach(() => {
    jest.clearAllMocks();
    failing = false;
  });
  afterAll(() => {
    error.mockRestore();
    warn.mockRestore();
  });

  it("shows the screen's error view while the chat under it stays", async () => {
    await openProfileThatThrows(ScreenErrorBoundary);

    expect(screen.getByText("common.screen_error_title")).toBeTruthy();
    expect(screen.getByText("common.screen_error_body")).toBeTruthy();
    expect(screen.getByText("chat screen", { includeHiddenElements: true })).toBeTruthy();
    expect(screen.queryByText("profile page")).toBeNull();
  });

  it("draws the screen again on Try again", async () => {
    await openProfileThatThrows(ScreenErrorBoundary);
    failing = false;

    await fireEvent.press(screen.getByRole("button", { name: "common.try_again" }));

    expect(screen.getByText("profile page")).toBeTruthy();
    expect(screen.queryByText("common.screen_error_title")).toBeNull();
  });

  it("reports the crash once, with the route and never its values", async () => {
    await renderRouter(routes(ScreenErrorBoundary), { initialUrl: "/" });
    failing = true;
    await act(async () => router.push("/memory/area:private-topic"));
    await act(async () => router.setParams({ key: "area:private-topic" }));
    // Another screen opens over it (a notification's link): still the one report.
    await act(async () => router.push("/"));

    expect(screen.getByText("common.screen_error_title", { includeHiddenElements: true })).toBeTruthy();
    expect(reportBoundaryError).toHaveBeenCalledTimes(1);
    expect(reportBoundaryError).toHaveBeenCalledWith(
      "screen",
      expect.objectContaining({ message: "profile render failed" }),
      null,
      "memory/[key]",
    );
    expect(JSON.stringify(jest.mocked(reportBoundaryError).mock.calls)).not.toContain("private");
  });

  it("without its own boundary, took the whole app to the root's", async () => {
    await openProfileThatThrows();

    expect(screen.queryByText("chat screen", { includeHiddenElements: true })).toBeNull();
    expect(screen.queryByText("common.screen_error_title")).toBeNull();
    expect(reportBoundaryError).not.toHaveBeenCalled();
  });
});
