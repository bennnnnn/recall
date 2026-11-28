/**
 * The offline banner lay over the screen (position absolute, top 0) and covered its
 * header: the drawer button, New chat, Back. It now takes its own room above the screens,
 * whose safe area is their own frame's, while a layer over the window keeps the window's.
 */
import { useEffect } from "react";
import { StyleSheet, Text } from "react-native";
import { act, render } from "@testing-library/react-native";
import { SafeAreaInsetsContext, useSafeAreaInsets } from "react-native-safe-area-context";

import * as ts from "typescript";

import { OfflineFrame } from "@/components/OfflineBanner";
import { MoleculeRotateModal } from "@/components/rich/MoleculeRotateModal";
import type { ConnectivityStatus } from "@/lib/networkProbe";
import { useWindowInsets, WindowInsetsScope } from "@/ui/hooks/useWindowInsets";

declare const __dirname: string;
const ROOT = ts.sys.resolvePath(`${__dirname}/../..`);
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

it("keeps a full-screen page's close button clear of the notch while the banner shows", async () => {
  // The molecule viewer reads its insets outside its modal, under the screens' frame.
  const view = await render(
    <SafeAreaInsetsContext.Provider value={WINDOW}>
      <OfflineFrame status="no_internet">
        <MoleculeRotateModal visible onClose={jest.fn()} onGrant={jest.fn()} onMove={jest.fn()}>
          {() => null}
        </MoleculeRotateModal>
      </OfflineFrame>
    </SafeAreaInsetsContext.Provider>,
  );
  expect(view.getByTestId("molecule-rotate-close")).toBeTruthy();
  type Node = { props?: { style?: unknown }; children?: (Node | string)[] | null };
  const tops: unknown[] = [];
  const walk = (node: Node | string | null) => {
    if (!node || typeof node === "string") return;
    const top = (StyleSheet.flatten(node.props?.style as never) as { marginTop?: number } | undefined)?.marginTop;
    if (top !== undefined) tops.push(top);
    node.children?.forEach(walk);
  };
  walk(view.toJSON() as Node);
  // Its sheet starts below the status bar (47), not at the frame's 0 (which drew it at 8).
  expect(tops).toContain(WINDOW.top);
});

it("has every full-screen page's owner read the window's insets, not its screen's", () => {
  // The page covers the window, so its top bar clears the status bar whatever the screens' frame says.
  const owners = ts.sys
    .readDirectory(ROOT, [".tsx"], ["node_modules", "**/__tests__"])
    .filter((file) => /<FullScreenModal\b/.test(ts.sys.readFile(file) ?? ""));
  expect(owners.length).toBeGreaterThan(4);
  const screenInsets = owners.filter((file) => /useSafeAreaInsets\(/.test(ts.sys.readFile(file) ?? ""));
  expect(screenInsets.map((file) => file.slice(ROOT.length + 1))).toEqual([]);
});
