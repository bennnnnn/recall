/**
 * The offline banner lay over the screen (position absolute, top 0) and covered its
 * header: the drawer button, New chat, Back. It now takes its own room above the screens,
 * whose safe area is their own frame's, while a layer over the window keeps the window's.
 */
import { useEffect } from "react";
import { StyleSheet, Text } from "react-native";
import { act, render } from "@testing-library/react-native";
import { SafeAreaInsetsContext, useSafeAreaInsets } from "react-native-safe-area-context";

import { OfflineFrame } from "@/components/OfflineBanner";
import type { ConnectivityStatus } from "@/lib/networkProbe";
import { useWindowInsets, WindowInsetsScope } from "@/ui/hooks/useWindowInsets";

const WINDOW = { top: 47, bottom: 34, left: 0, right: 0 };
const seen = { screenTop: -1, windowTop: -1, layerTop: -1, mounts: 0 };
const record = (values: Partial<typeof seen>) => Object.assign(seen, values);
const mounted = () => {
  seen.mounts += 1;
};

function Screen() {
  record({ screenTop: useSafeAreaInsets().top, windowTop: useWindowInsets().top });
  useEffect(mounted, []);
  return <Text>screen</Text>;
}

function Layer() {
  record({ layerTop: useSafeAreaInsets().top });
  return null;
}

const app = (status: ConnectivityStatus) => (
  <SafeAreaInsetsContext.Provider value={WINDOW}>
    <OfflineFrame status={status}>
      <Screen />
      <WindowInsetsScope>
        <Layer />
      </WindowInsetsScope>
    </OfflineFrame>
  </SafeAreaInsetsContext.Provider>
);

beforeEach(() => {
  seen.mounts = 0;
});

it("puts the banner above the screens, never over their header", async () => {
  const view = await render(app("no_internet"));
  const banner = StyleSheet.flatten(view.getByTestId("offline-banner").props.style);
  expect(banner.position).not.toBe("absolute");
  // The banner covers the status bar itself.
  expect(banner.paddingTop).toBeGreaterThanOrEqual(WINDOW.top);
  // The screens read their own frame's safe area; a layer over the window, the window's.
  expect(seen.screenTop).toBe(0);
  expect(seen.windowTop).toBe(WINDOW.top);
  expect(seen.layerTop).toBe(WINDOW.top);
});

it("keeps the screens mounted as the connection comes and goes", async () => {
  const view = await render(app("online"));
  expect(view.queryByTestId("offline-banner")).toBeNull();
  await act(async () => view.rerender(app("no_internet")));
  expect(view.getByTestId("offline-banner")).toBeTruthy();
  await act(async () => view.rerender(app("online")));
  expect(seen.mounts).toBe(1);
});
