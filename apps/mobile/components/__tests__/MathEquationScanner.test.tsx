import React from "react";
import { act, fireEvent, render } from "@testing-library/react-native";

import { MathEquationScanner } from "@/components/MathEquationScanner";
import { lightTheme as mockLightTheme } from "@/lib/theme";

const mockTakePictureAsync = jest.fn(async () => ({
  uri: "file:///shot.jpg",
  width: 800,
  height: 1200,
}));
const mockPermission = { granted: true, canAskAgain: true };

jest.mock("expo-camera", () => {
  const ReactNative = require("react");
  const { View } = require("react-native");
  const CameraView = ReactNative.forwardRef(
    (props: { onCameraReady?: () => void; style?: object }, ref: unknown) => {
      ReactNative.useImperativeHandle(ref, () => ({ takePictureAsync: mockTakePictureAsync }));
      ReactNative.useEffect(() => {
        props.onCameraReady?.();
      }, [props.onCameraReady]);
      return ReactNative.createElement(View, { style: props.style });
    },
  );
  CameraView.displayName = "CameraView";
  return {
    CameraView,
    useCameraPermissions: () => [mockPermission, jest.fn()],
  };
});

jest.mock("expo-image-manipulator", () => ({
  SaveFormat: { JPEG: "jpeg" },
  manipulateAsync: jest.fn(async () => ({ uri: "file:///cropped.jpg" })),
}));

jest.mock("@/lib/lastPhotoThumbnail", () => ({
  loadLastPhotoUri: jest.fn(async () => null),
  useLastPhotoThumb: () => null,
}));

jest.mock("@/lib/attachments", () => ({
  pickFromPhotoLibrary: jest.fn(async () => null),
  HeicUnsupportedError: class extends Error {},
  NativePickerBusyError: class extends Error {},
  NativePickerTimeoutError: class extends Error {},
  PhotoLibraryPermissionError: class extends Error {
    needsSettings = false;
  },
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 47, bottom: 34, left: 0, right: 0 }),
}));
jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));
jest.mock("@/lib/haptics", () => ({
  impactMedium: jest.fn(),
  selection: jest.fn(),
  tap: jest.fn(),
}));
jest.mock("@/lib/scheduleIdle", () => ({
  scheduleIdlePromise: () => Promise.resolve(),
}));
jest.mock("@/lib/reduceMotion", () => ({
  useReduceMotion: () => false,
}));

describe("MathEquationScanner", () => {
  beforeEach(() => {
    mockTakePictureAsync.mockClear();
    mockPermission.granted = true;
    mockPermission.canAskAgain = true;
  });

  it("keeps the Modal mounted when visible goes false", async () => {
    const view = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    expect(view.getByTestId("math-scanner-modal")).toBeTruthy();
    view.rerender(
      <MathEquationScanner visible={false} onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    expect(
      view.getByTestId("math-scanner-modal", { includeHiddenElements: true }),
    ).toBeTruthy();
  });

  it("shows Photos and a labeled shutter when the camera is granted", async () => {
    const { getByTestId, getByLabelText } = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    expect(getByTestId("math-scanner-photos")).toBeTruthy();
    expect(getByLabelText("chat.math_scan_capture_a11y")).toBeTruthy();
    expect(getByLabelText("chat.math_scan_reset_frame")).toBeTruthy();
    expect(getByTestId("math-scanner-camera")).toBeTruthy();
  });

  it("labels the permission CTA when the camera is denied", async () => {
    mockPermission.granted = false;
    const { getByTestId, getByLabelText } = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    expect(getByTestId("math-scanner-permission")).toBeTruthy();
    expect(getByLabelText("chat.math_scan_allow_camera")).toBeTruthy();
  });

  it("keeps CameraView mounted after capture so retake does not remount", async () => {
    const { getByTestId, getByLabelText } = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    await act(async () => {
      fireEvent.press(getByLabelText("chat.math_scan_capture_a11y"));
    });
    expect(mockTakePictureAsync).toHaveBeenCalled();
    expect(getByTestId("math-scanner-camera")).toBeTruthy();
    expect(getByLabelText("chat.math_scan_retake")).toBeTruthy();
  });
});
