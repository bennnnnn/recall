import React from "react";
import { act, render } from "@testing-library/react-native";

import { LiveMathScannerCamera } from "@/features/scanner/components/LiveMathScannerCamera";
import { nativeScannerLinked } from "@/features/scanner/model/nativeCamera";

jest.mock("@/features/scanner/model/nativeCamera", () => ({ nativeScannerLinked: jest.fn() }));

/**
 * How the native camera module loads. Metro does not reject `import()` of a module that
 * throws while loading: it reports the error and resolves a module without its exports
 * ("empty"), which is what the Simulator build without ML Kit did.
 */
const mockNative: { mode: "ok" | "empty" | "throws"; loads: number } = { mode: "ok", loads: 0 };

jest.mock("@/features/scanner/components/LiveMathScannerCameraNative", () => {
  const ReactNative = jest.requireActual<typeof import("react")>("react");
  const { View: HostView } = jest.requireActual<typeof import("react-native")>("react-native");
  const Native = ReactNative.forwardRef(function MockNative(_props: object, _ref: React.Ref<unknown>) {
    return ReactNative.createElement(HostView, { testID: "native-camera" });
  });
  return {
    __esModule: true,
    get LiveMathScannerCameraNative() {
      mockNative.loads += 1;
      if (mockNative.mode === "throws") throw new Error("NitroModules are not available in Expo Go");
      return mockNative.mode === "ok" ? Native : undefined;
    },
  };
});

const props = {
  active: true,
  torchOn: false,
  zoom: 0,
  scanRegion: { x: 0.1, y: 0.3, width: 0.8, height: 0.3 },
  viewSize: { width: 390, height: 844 },
  subject: "math" as const,
  readEpoch: 0,
  onReady: jest.fn(),
  onError: jest.fn(),
  onDetectionChange: jest.fn(),
};

async function settle() {
  await act(async () => {
    for (let i = 0; i < 5; i += 1) await Promise.resolve();
  });
}

beforeEach(() => {
  mockNative.mode = "ok";
  mockNative.loads = 0;
  props.onError.mockClear();
  jest.mocked(nativeScannerLinked).mockResolvedValue(true);
});

it("does not load the camera's modules in a build without them, and says so once", async () => {
  jest.mocked(nativeScannerLinked).mockResolvedValue(false);
  const onUnavailable = jest.fn();
  const view = await render(<LiveMathScannerCamera {...props} onUnavailable={onUnavailable} />);
  await settle();
  // A new handler identity must not load the camera again.
  await view.rerender(<LiveMathScannerCamera {...props} onUnavailable={jest.fn()} />);
  await settle();
  expect(onUnavailable).toHaveBeenCalledTimes(1);
  expect(mockNative.loads).toBe(0);
  expect(props.onError).not.toHaveBeenCalled();
  expect(view.queryByTestId("native-camera")).toBeNull();
});

it.each(["empty", "throws"] as const)(
  "reports a camera module that loads %s as unavailable, not as a camera error",
  async (mode) => {
    mockNative.mode = mode;
    const onUnavailable = jest.fn();
    const view = await render(<LiveMathScannerCamera {...props} onUnavailable={onUnavailable} />);
    await settle();
    expect(onUnavailable).toHaveBeenCalledTimes(1);
    expect(props.onError).not.toHaveBeenCalled();
    expect(view.queryByTestId("native-camera")).toBeNull();
  },
);

it("draws the native camera where the build has it", async () => {
  const onUnavailable = jest.fn();
  const view = await render(<LiveMathScannerCamera {...props} onUnavailable={onUnavailable} />);
  await settle();
  expect(view.getByTestId("native-camera")).toBeTruthy();
  expect(onUnavailable).not.toHaveBeenCalled();
});
