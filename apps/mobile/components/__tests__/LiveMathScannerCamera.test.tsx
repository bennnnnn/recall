import { createRef } from "react";
import { TurboModuleRegistry } from "react-native";

import { render, waitFor } from "@testing-library/react-native";

import {
  LiveMathScannerCamera,
  type LiveScannerCameraHandle,
} from "@/components/mathScanner/LiveMathScannerCamera";

const mockTakePictureAsync = jest.fn(async () => ({
  uri: "file:///expo.jpg",
  width: 100,
  height: 200,
}));

jest.mock("expo-camera", () => {
  const React = jest.requireActual<typeof import("react")>("react");
  const { View } = jest.requireActual<typeof import("react-native")>("react-native");
  const CameraView = React.forwardRef(
    (
      { onCameraReady }: { onCameraReady?: () => void },
      ref: React.Ref<{ takePictureAsync: typeof mockTakePictureAsync }>,
    ) => {
      React.useImperativeHandle(ref, () => ({ takePictureAsync: mockTakePictureAsync }));
      React.useEffect(() => {
        onCameraReady?.();
      }, [onCameraReady]);
      return React.createElement(View, { testID: "expo-scanner-camera" });
    },
  );
  CameraView.displayName = "CameraView";
  return { CameraView };
});

jest.mock("@/components/mathScanner/LiveMathScannerCameraNative", () => {
  throw new Error("native scanner must not load without Nitro");
});

const scanRegion = { x: 0.1, y: 0.2, width: 0.8, height: 0.3 };

describe("LiveMathScannerCamera", () => {
  beforeEach(() => {
    mockTakePictureAsync.mockClear();
    jest.spyOn(TurboModuleRegistry, "get").mockImplementation((name) => {
      if (name === "NitroModules") return null;
      return null;
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("uses expo-camera when Nitro is missing", async () => {
    const onReady = jest.fn();
    const onError = jest.fn();
    const ref = createRef<LiveScannerCameraHandle>();

    const view = await render(
      <LiveMathScannerCamera
        ref={ref}
        active
        torchOn={false}
        zoom={0}
        scanRegion={scanRegion}
        onReady={onReady}
        onError={onError}
        onDetectionChange={jest.fn()}
      />,
    );

    await waitFor(() => expect(onReady).toHaveBeenCalled());
    expect(view.getByTestId("expo-scanner-camera")).toBeTruthy();
    expect(onError).not.toHaveBeenCalled();

    const photo = await ref.current?.takePictureAsync();
    expect(photo).toEqual({ uri: "file:///expo.jpg", width: 100, height: 200 });
    expect(mockTakePictureAsync).toHaveBeenCalledWith({ quality: 0.92, shutterSound: true });
  });
});
