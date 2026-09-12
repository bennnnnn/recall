import React from "react";
import { Dimensions, Image } from "react-native";
import * as ImageManipulator from "expo-image-manipulator";

import { pickFromPhotoLibrary } from "@/lib/attachments";
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


describe("imported math scanner photos", () => {
  beforeEach(() => {
    mockPermission.granted = true;
    mockPermission.canAskAgain = true;
    jest.spyOn(Dimensions, "get").mockReturnValue({ width: 390, height: 844, scale: 3, fontScale: 1 });
    jest.spyOn(Image, "getSize").mockImplementation(async (_uri, success) => {
      success?.(1200, 700);
      return { width: 1200, height: 700 };
    });
    jest.mocked(pickFromPhotoLibrary).mockResolvedValue({
      localUri: "file:///landscape.png", contentType: "image/png", fileName: "landscape.png", kind: "image",
    });
    jest.mocked(ImageManipulator.manipulateAsync).mockClear();
  });
  afterEach(() => jest.restoreAllMocks());

  it.each([true, false])("shows and sends the whole imported image with camera permission=%s", async (granted) => {
    mockPermission.granted = granted;
    const onCaptured = jest.fn();
    const { getByLabelText, getByTestId, queryByTestId } = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={onCaptured} />,
    );
    await act(async () => {
      fireEvent.press(getByLabelText("chat.math_scan_photos_a11y"));
    });
    const preview = getByTestId("math-scanner-preview");
    expect(preview.props.resizeMode).toBe("contain");
    expect(preview.props.style.width / preview.props.style.height).toBeCloseTo(1200 / 700, 10);
    expect(queryByTestId("math-scanner-permission")).toBeNull();
    await act(async () => {
      fireEvent.press(getByLabelText("chat.math_scan_solve"));
    });
    expect(ImageManipulator.manipulateAsync).toHaveBeenCalledWith(
      "file:///landscape.png",
      [{ crop: { originX: 0, originY: 0, width: 1200, height: 700 } }],
      { compress: 0.9, format: "jpeg" },
    );
    expect(onCaptured).toHaveBeenCalledWith(expect.objectContaining({ localUri: "file:///cropped.jpg" }));
  });

  it("keeps a captured camera photo on the existing cover preview", async () => {
    const { getByLabelText, getByTestId } = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    await act(async () => {
      fireEvent.press(getByLabelText("chat.math_scan_capture_a11y"));
    });
    expect(getByTestId("math-scanner-preview").props.resizeMode).toBe("cover");
  });
});
