import React from "react";
import { AppState, type AppStateStatus, Dimensions, StyleSheet } from "react-native";
import { deleteAsync } from "expo-file-system/legacy";

import { pickFromPhotoLibrary, pickImageDocument } from "@/features/attachments/model/attachments";
import { act, fireEvent, render, waitFor, within } from "@testing-library/react-native";

import { MathEquationScanner } from "@/features/scanner/components/MathEquationScanner";
import { CAMERA_ERROR_GRACE_MS, CAMERA_START_TIMEOUT_MS } from "@/features/scanner/model/cameraStatus";
import * as contentFit from "@/features/scanner/model/contentFit";
import { shotCutMaxEdge } from "@/features/scanner/model/contentFit";
import { readTextLines } from "@/features/scanner/model/readTextLines";
import { cropScanImage, measureScanImage, SCAN_MAX_EDGE } from "@/features/scanner/model/scanImage";
import { selection } from "@/lib/haptics";
import { playScannerSwitchCue, useScannerSwitchCue } from "@/features/scanner/model/switchCue";
import { AA, compositeOver, contrastRatio } from "@/lib/__tests__/support/contrast";

const mockTakePictureAsync = jest.fn(async (): Promise<{ uri: string } | null> => ({
  uri: "file:///shot.jpg",
}));
/** Decoded sizes by file, as the manipulator reports them. */
const MOCK_SIZES: Record<string, { width: number; height: number }> = {
  "file:///shot.jpg": { width: 800, height: 1200 },
  "file:///landscape.png": { width: 1200, height: 700 },
  // A capture cut to the live frame.
  "file:///cropped.jpg": { width: 640, height: 300 },
};
const mockPermission = { granted: true, canAskAgain: true };
/** False: the mock camera never says it started (no device, or still starting). */
const mockCamera = { startsReady: true };

/** The permission hook's read: what the phone's settings say now. */
const mockReadPermission = jest.fn(async () => mockPermission);

jest.mock("expo-image-picker", () => ({
  useCameraPermissions: () => [mockPermission, jest.fn(), mockReadPermission],
}));

jest.mock("@/features/scanner/components/LiveMathScannerCamera", () => {
  const ReactNative = jest.requireActual<typeof import("react")>("react");
  const { View } = jest.requireActual<typeof import("react-native")>("react-native");
  const LiveMathScannerCamera = ReactNative.forwardRef(
    (
      props: {
        onReady?: () => void;
        onError?: (error: Error) => void;
        onUnavailable?: () => void;
        onDetectionChange?: (detection: {
          hasText: boolean;
          stable: boolean;
          text: string;
        }) => void;
      },
      ref: React.Ref<unknown>,
    ) => {
      ReactNative.useImperativeHandle(ref, () => ({ takePictureAsync: mockTakePictureAsync, focusAt: jest.fn() }));
      ReactNative.useEffect(() => {
        let cancelled = false;
        queueMicrotask(() => {
          if (!cancelled && mockCamera.startsReady) props.onReady?.();
        });
        return () => {
          cancelled = true;
        };
      }, [props.onReady]);
      // The camera's callbacks ride on the host view, where the tests call them.
      const callbacks = {
        onDetectionChange: props.onDetectionChange,
        onReady: props.onReady,
        onError: props.onError,
        onUnavailable: props.onUnavailable,
      };
      return ReactNative.createElement(View, { testID: "mock-live-scanner-camera", ...callbacks });
    },
  );
  LiveMathScannerCamera.displayName = "LiveMathScannerCamera";
  return { LiveMathScannerCamera };
});

jest.mock("expo-image-manipulator", () => ({
  ImageManipulator: {},
  SaveFormat: { JPEG: "jpeg" },
}));
jest.mock("expo-file-system/legacy", () => ({ deleteAsync: jest.fn(async () => undefined) }));
// The phone reads no text from a still unless a test says it does.
jest.mock("@/features/scanner/model/readTextLines", () => ({ readTextLines: jest.fn(async () => []) }));
jest.mock("@/features/scanner/model/scanImage", () => ({
  ...jest.requireActual("@/features/scanner/model/scanImage"),
  cropScanImage: jest.fn(),
  measureScanImage: jest.fn(),
}));

function mockScanImages() {
  jest.mocked(measureScanImage).mockImplementation(async (uri) => MOCK_SIZES[uri]);
  jest.mocked(cropScanImage).mockImplementation(async (uri, cropFor) => {
    const crop = cropFor(MOCK_SIZES[uri]);
    return { uri: "file:///cropped.jpg", width: crop.width, height: crop.height };
  });
}

function deletedFiles(): string[] {
  return jest.mocked(deleteAsync).mock.calls.map(([uri]) => uri);
}

jest.mock("expo-linear-gradient", () => {
  return { LinearGradient: "LinearGradient" };
});

jest.mock("@/features/attachments/model/attachments", () => ({
  pickFromPhotoLibrary: jest.fn(async () => null),
  pickImageDocument: jest.fn(async () => null),
  NativePickerBusyError: class extends Error {},
  NativePickerTimeoutError: class extends Error {},
  PhotoLibraryPermissionError: class extends Error {
    needsSettings = false;
  },
}));

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 47, bottom: 34, left: 0, right: 0 }),
}));
const mockTheme = { dark: false };
jest.mock("@/lib/theme", () => {
  const actual = jest.requireActual("@/lib/theme");
  return { ...actual, useTheme: () => (mockTheme.dark ? actual.darkTheme : actual.lightTheme) };
});
jest.mock("@/lib/haptics", () => ({
  impactMedium: jest.fn(),
  selection: jest.fn(),
  tap: jest.fn(),
}));
jest.mock("@/features/scanner/model/switchCue", () => ({
  playScannerSwitchCue: jest.fn(async () => undefined),
  useScannerSwitchCue: jest.fn(),
  stopScannerSwitchCue: jest.fn(),
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
    jest.mocked(cropScanImage).mockClear();
    jest.mocked(deleteAsync).mockClear();
    mockScanImages();
    mockPermission.granted = true;
    mockPermission.canAskAgain = true;
    mockCamera.startsReady = true;
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

  it("keeps the shutter disc while the photo library is opening", async () => {
    let release: (picked: null) => void = () => undefined;
    jest.mocked(pickFromPhotoLibrary).mockImplementation(
      () =>
        new Promise((resolve) => {
          release = resolve;
        }),
    );
    const view = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    await act(async () => {
      fireEvent.press(view.getByTestId("math-scanner-photos"));
    });
    expect(view.getByTestId("math-scanner-shutter-disc")).toBeTruthy();
    await act(async () => {
      release(null);
    });
    jest.mocked(pickFromPhotoLibrary).mockResolvedValue(null);
  });

  it("shows a live crop frame with the selector and torch beside the shutter", async () => {
    const { getByTestId, getByLabelText, queryByLabelText, queryByTestId } = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    expect(getByTestId("math-scanner-photos")).toBeTruthy();
    expect(getByLabelText("chat.math_scan_capture_a11y")).toBeTruthy();
    expect(queryByLabelText("chat.math_scan_reset_frame")).toBeNull();
    expect(getByTestId("scanner-subject-switcher")).toBeTruthy();
    expect(getByLabelText("chat.math_scan_frame_a11y")).toBeTruthy();
    expect(queryByTestId("math-scanner-shimmer")).toBeNull();
    expect(getByTestId("math-scanner-torch").parent?.parent).toBe(
      getByTestId("math-scanner-shutter").parent,
    );
    expect(getByTestId("math-scanner-camera")).toBeTruthy();
    expect(getByTestId("mock-live-scanner-camera")).toBeTruthy();
    expect(getByTestId("math-scanner-frame-idle")).toBeTruthy();
    // Every edge and corner of the frame pulls out.
    for (const handle of ["tl", "t", "tr", "r", "br", "b", "bl", "l"]) {
      expect(getByTestId(`math-scanner-handle-${handle}`)).toBeTruthy();
    }
    // Each subject tab keeps its name on one line, in a row that scrolls sideways.
    expect(getByTestId("scanner-subject-switcher").props.horizontal).toBe(true);
    expect(within(getByTestId("scanner-subject-chemistry")).getByText("chat.math_scan_subject_chemistry").props.numberOfLines).toBe(1);
    // The subject's mark sits in the shutter, not over the viewfinder.
    expect(within(getByTestId("math-scanner-shutter")).getByTestId("scanner-subject-mark-math")).toBeTruthy();
    expect(queryByTestId("scanner-subject-guide-math")).toBeNull();
  });

  it("marks the live frame ready after stable on-device OCR", async () => {
    const view = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    const nativeCamera = view.getByTestId("mock-live-scanner-camera");
    await act(async () => {
      nativeCamera.props.onDetectionChange?.({
        hasText: true,
        stable: true,
        text: "2x + 3 = 7",
      });
    });
    expect(view.getByTestId("math-scanner-frame-ready")).toBeTruthy();
    expect(selection).toHaveBeenCalled();
  });

  function shutterState(view: Awaited<ReturnType<typeof render>>) {
    return view.getByTestId("math-scanner-shutter").props.accessibilityState;
  }

  it.each([
    ["missing", "onUnavailable", "chat.math_scan_camera_needs_build"],
    ["failed", "onError", "chat.math_scan_camera_unavailable"],
  ] as const)(
    "shows a %s camera in the viewfinder and offers a photo instead",
    async (reason, signal, words) => {
      jest.mocked(pickFromPhotoLibrary).mockClear();
      mockCamera.startsReady = false;
      const view = await render(
        <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
      );
      jest.useFakeTimers();
      try {
        await act(async () => {
          view.getByTestId("mock-live-scanner-camera").props[signal]?.(new Error("Camera is in use"));
        });
        await act(async () => {
          jest.advanceTimersByTime(CAMERA_ERROR_GRACE_MS);
        });
      } finally {
        jest.useRealTimers();
      }
      const panel = within(view.getByTestId(`math-scanner-camera-unavailable-${reason}`));
      expect(panel.getByText(words)).toBeTruthy();
      // The black frame's aiming aids go; the shutter is visibly off, never a silent tap.
      expect(view.queryByLabelText("chat.math_scan_frame_a11y")).toBeNull();
      expect(view.getByTestId("math-scanner-shutter-unavailable")).toBeTruthy();
      expect(shutterState(view)).toMatchObject({ disabled: true });
      await act(async () => {
        fireEvent.press(view.getByTestId("math-scanner-shutter"));
      });
      expect(mockTakePictureAsync).not.toHaveBeenCalled();
      await act(async () => {
        fireEvent.press(panel.getByTestId("math-scanner-unavailable-photos"));
      });
      expect(pickFromPhotoLibrary).toHaveBeenCalledTimes(1);
      expect(view.queryByTestId("math-scanner-error")).toBeNull();
    },
  );

  it("shows nothing for an error while the camera starts when it starts a moment later", async () => {
    // On the S23 the zoom and torch, set before the camera opened, came back as errors and
    // "couldn't start the camera" flashed on every open until it started half a second later.
    mockCamera.startsReady = false;
    const view = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    jest.useFakeTimers();
    try {
      const camera = view.getByTestId("mock-live-scanner-camera");
      await act(async () => {
        camera.props.onError(new Error("Camera is not active."));
        camera.props.onError(new Error("Camera is not active."));
      });
      await act(async () => {
        jest.advanceTimersByTime(CAMERA_ERROR_GRACE_MS - 100);
      });
      expect(view.queryByTestId("math-scanner-camera-unavailable-failed")).toBeNull();
      expect(view.getByTestId("math-scanner-shutter-starting")).toBeTruthy();
      await act(async () => {
        camera.props.onReady();
      });
      await act(async () => {
        jest.advanceTimersByTime(CAMERA_START_TIMEOUT_MS);
      });
      expect(view.queryByTestId("math-scanner-camera-unavailable-failed")).toBeNull();
      expect(shutterState(view)).toMatchObject({ disabled: false });
    } finally {
      jest.useRealTimers();
    }
  });

  it("keeps a running camera running through an error", async () => {
    const view = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    await waitFor(() => expect(shutterState(view)).toMatchObject({ disabled: false }));
    jest.useFakeTimers();
    try {
      await act(async () => {
        view.getByTestId("mock-live-scanner-camera").props.onError(new Error("Camera is not active."));
      });
      await act(async () => {
        jest.advanceTimersByTime(CAMERA_START_TIMEOUT_MS);
      });
      expect(view.queryByTestId("math-scanner-camera-unavailable-failed")).toBeNull();
      expect(shutterState(view)).toMatchObject({ disabled: false });
    } finally {
      jest.useRealTimers();
    }
  });

  it("shows the subject's mark on a dimmed shutter until the camera is ready, then captures", async () => {
    mockCamera.startsReady = false;
    const view = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    expect(view.getByTestId("math-scanner-shutter-starting")).toBeTruthy();
    expect(shutterState(view)).toMatchObject({ disabled: true, busy: true });
    expect(view.getByTestId("math-scanner-shutter").props.accessibilityHint).toBe(
      "chat.math_scan_camera_starting",
    );
    // The mark is there from the first frame, not after the camera starts (2026-11-13).
    expect(view.getByTestId("scanner-subject-mark-math")).toBeTruthy();
    await act(async () => {
      fireEvent.press(view.getByTestId("math-scanner-shutter"));
    });
    expect(mockTakePictureAsync).not.toHaveBeenCalled();
    await act(async () => {
      view.getByTestId("mock-live-scanner-camera").props.onReady?.();
    });
    expect(view.getByTestId("math-scanner-shutter-ready")).toBeTruthy();
    expect(shutterState(view)).toMatchObject({ disabled: false });
    await act(async () => {
      fireEvent.press(view.getByTestId("math-scanner-shutter"));
    });
    expect(mockTakePictureAsync).toHaveBeenCalledTimes(1);
  });

  it("treats a camera that never starts as unavailable, and a late start as ready", async () => {
    jest.useFakeTimers();
    mockCamera.startsReady = false;
    const view = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    try {
      await act(async () => {
        jest.advanceTimersByTime(3_900);
      });
      expect(view.queryByTestId("math-scanner-camera-unavailable-timeout")).toBeNull();
      await act(async () => {
        jest.advanceTimersByTime(200);
      });
      const panel = within(view.getByTestId("math-scanner-camera-unavailable-timeout"));
      expect(panel.getByText("chat.math_scan_camera_off")).toBeTruthy();
      expect(panel.getByText("chat.math_scan_choose_photo")).toBeTruthy();
      expect(shutterState(view)).toMatchObject({ disabled: true });
      await act(async () => {
        view.getByTestId("mock-live-scanner-camera").props.onReady?.();
      });
      expect(view.queryByTestId("math-scanner-camera-unavailable-timeout")).toBeNull();
      expect(shutterState(view)).toMatchObject({ disabled: false });
    } finally {
      view.unmount();
      jest.useRealTimers();
    }
  });

  it("leaves a camera that is ready unchanged: no message, the live frame, a working shutter", async () => {
    // The camera's ready signal is a microtask; only the clock is faked.
    jest.useFakeTimers({ doNotFake: ["queueMicrotask"] });
    const view = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    try {
      await act(async () => {
        jest.advanceTimersByTime(10_000);
      });
      expect(view.queryByTestId(/math-scanner-camera-unavailable/)).toBeNull();
      expect(view.getByTestId("math-scanner-shutter-ready")).toBeTruthy();
      expect(view.getByTestId("math-scanner-shutter-disc")).toBeTruthy();
      expect(view.getByLabelText("chat.math_scan_frame_a11y")).toBeTruthy();
      expect(shutterState(view)).toMatchObject({ disabled: false, busy: false });
    } finally {
      view.unmount();
      jest.useRealTimers();
    }
  });

  // Danger ink on the 65% scrim over a white page measured 1.45:1 light, 2.52 dark.
  it.each([
    ["light", false],
    ["dark", true],
  ] as const)("keeps a scan error readable over a white page in %s mode", async (_scheme, dark) => {
    mockTheme.dark = dark;
    mockTakePictureAsync.mockResolvedValueOnce(null);
    try {
      const view = await render(
        <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
      );
      await act(async () => {
        fireEvent.press(view.getByLabelText("chat.math_scan_capture_a11y"));
      });
      const plate = view.getByTestId("math-scanner-error");
      const ink = String(StyleSheet.flatten(within(plate).getByText("chat.math_scan_failed").props.style).color);
      const scrim = String(StyleSheet.flatten(plate.props.style).backgroundColor);
      expect(contrastRatio(ink, compositeOver(scrim, "#FFFFFF"))).toBeGreaterThanOrEqual(AA);
      // Without red ink, an icon says it is an error.
      expect(within(plate).getByTestId("math-scanner-error-icon").props).toMatchObject({
        name: "alert-circle",
        color: ink,
      });
    } finally {
      mockTheme.dark = false;
    }
  });

  it("switches to physics with one directional sound and haptic cue", async () => {
    const { getByTestId } = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    // The cues load as the scanner opens, so the first switch is heard.
    expect(useScannerSwitchCue).toHaveBeenCalledWith(true);
    await act(async () => {
      fireEvent.press(getByTestId("scanner-subject-physics"));
    });
    expect(selection).toHaveBeenCalled();
    expect(playScannerSwitchCue).toHaveBeenCalledWith(1);
    expect(within(getByTestId("math-scanner-shutter")).getByTestId("scanner-subject-mark-physics")).toBeTruthy();
  });

  it("takes a chemistry shot to the crop screen and sends it as chemistry on Solve", async () => {
    const onCaptured = jest.fn();
    const view = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={onCaptured} />,
    );
    await act(async () => {
      fireEvent.press(view.getByTestId("scanner-subject-chemistry"));
    });
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_capture_a11y"));
    });
    expect(onCaptured).not.toHaveBeenCalled();
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_solve"));
    });
    expect(onCaptured).toHaveBeenCalledTimes(1);
    expect(onCaptured).toHaveBeenCalledWith(
      expect.objectContaining({ localUri: "file:///cropped.jpg" }),
      "chemistry",
    );
  });

  it("shows biology's mark in the shutter when biology is selected", async () => {
    const { getByTestId } = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    await act(async () => {
      fireEvent.press(getByTestId("scanner-subject-biology"));
    });
    expect(within(getByTestId("math-scanner-shutter")).getByTestId("scanner-subject-mark-biology")).toBeTruthy();
    expect(getByTestId("scanner-subject-biology").props.accessibilityState).toEqual({ selected: true });
  });

  it("does not take hidden camera photos while the scanner is idle", async () => {
    jest.useFakeTimers();
    const view = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    try {
      await act(async () => {
        jest.advanceTimersByTime(15_000);
        await Promise.resolve();
      });
      expect(mockTakePictureAsync).not.toHaveBeenCalled();
    } finally {
      view.unmount();
      jest.useRealTimers();
    }
  });

  it("labels the permission CTA when the camera is denied", async () => {
    mockPermission.granted = false;
    const { getByTestId, getByLabelText } = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    expect(getByTestId("math-scanner-permission")).toBeTruthy();
    expect(getByLabelText("chat.math_scan_allow_camera")).toBeTruthy();
  });

  it("asks the phone again when it opens and when the app comes back from Settings", async () => {
    mockPermission.granted = false;
    mockReadPermission.mockClear();
    const view = await render(<MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />);
    expect(mockReadPermission).toHaveBeenCalledTimes(1);
    expect(view.getByTestId("math-scanner-permission")).toBeTruthy();

    const appState = jest.mocked(AppState.addEventListener).mock.calls.at(-1)?.[1] as (state: AppStateStatus) => void;
    await act(async () => {
      appState("background");
      appState("active");
    });
    expect(mockReadPermission).toHaveBeenCalledTimes(2);

    await view.rerender(<MathEquationScanner visible={false} onClose={jest.fn()} onCaptured={jest.fn()} />);
    await view.rerender(<MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />);
    expect(mockReadPermission).toHaveBeenCalledTimes(3);
  });

  it("without the camera, reads an image from Photos or from Files", async () => {
    jest.mocked(pickFromPhotoLibrary).mockClear();
    jest.mocked(pickImageDocument).mockClear();
    mockPermission.granted = false;
    const view = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    await act(async () => {
      fireEvent.press(view.getByTestId("math-scanner-permission-photos"));
    });
    expect(pickFromPhotoLibrary).toHaveBeenCalledTimes(1);
    expect(pickImageDocument).not.toHaveBeenCalled();
    await act(async () => {
      fireEvent.press(view.getByTestId("math-scanner-permission-files"));
    });
    expect(pickImageDocument).toHaveBeenCalledTimes(1);
  });

  it("opens Photos on a tap and Files on a long press of the library button", async () => {
    jest.mocked(pickFromPhotoLibrary).mockClear();
    jest.mocked(pickImageDocument).mockClear();
    const view = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    await act(async () => {
      fireEvent.press(view.getByTestId("math-scanner-photos"));
    });
    expect(pickFromPhotoLibrary).toHaveBeenCalledTimes(1);
    await act(async () => {
      fireEvent(view.getByTestId("math-scanner-photos"), "longPress");
    });
    expect(pickImageDocument).toHaveBeenCalledTimes(1);
  });

  it("cuts a capture to the live frame and holds it on the crop screen until Solve", async () => {
    const onCaptured = jest.fn();
    const view = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={onCaptured} />,
    );
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_capture_a11y"));
    });
    expect(mockTakePictureAsync).toHaveBeenCalledTimes(1);
    // The cut keeps room around the frame, so it may be longer than a scan and still send the
    // aimed part at full size.
    expect(cropScanImage).toHaveBeenCalledWith("file:///shot.jpg", expect.any(Function), shotCutMaxEdge(SCAN_MAX_EDGE));
    // The framed shot, with its own crop frame, Retake and Solve; nothing is sent yet.
    expect(view.getByTestId("math-scanner-preview").props.source).toEqual({ uri: "file:///cropped.jpg" });
    expect(view.getByLabelText("chat.math_scan_frame_a11y")).toBeTruthy();
    expect(view.getByTestId("math-scanner-preview-retake")).toBeTruthy();
    expect(onCaptured).not.toHaveBeenCalled();
    // The full-resolution capture is deleted once cropped.
    expect(deletedFiles()).toEqual(["file:///shot.jpg"]);
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_solve"));
    });
    // Solve sends the crop straight to the chat: no reading step in between.
    expect(cropScanImage).toHaveBeenLastCalledWith("file:///cropped.jpg", expect.any(Function));
    expect(onCaptured).toHaveBeenCalledTimes(1);
    expect(onCaptured).toHaveBeenCalledWith(
      expect.objectContaining({ localUri: "file:///cropped.jpg" }),
      "math",
    );
  });

  it("keeps room around a capture, and Solve sends just what was aimed at", async () => {
    const shot = jest.spyOn(contentFit, "shotCrop");
    const view = await render(<MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />);
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_capture_a11y"));
    });
    const [frame] = shot.mock.calls[0]!;
    const { crop, aim } = shot.mock.results[0]!.value as ReturnType<typeof contentFit.shotCrop>;
    // The cut has room above and below the live frame, to widen the frame over a cut line.
    expect(crop.height).toBeGreaterThan(frame.height);
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_solve"));
    });
    const [, cropFor] = jest.mocked(cropScanImage).mock.calls.at(-1)!;
    const { width, height } = MOCK_SIZES["file:///cropped.jpg"]!;
    const sent = cropFor({ width, height });
    expect(sent.originX / width).toBeCloseTo(aim.x, 2);
    expect(sent.originY / height).toBeCloseTo(aim.y, 2);
    expect(sent.width / width).toBeCloseTo(aim.width, 2);
    expect(sent.height / height).toBeCloseTo(aim.height, 2);
    shot.mockRestore();
  });

  it("brings up the whole photo, framed where it was aimed, when a capture cannot be cut", async () => {
    const shot = jest.spyOn(contentFit, "shotCrop");
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    jest.mocked(cropScanImage).mockImplementationOnce(async (uri, cropFor) => {
      cropFor(MOCK_SIZES[uri]!);
      throw new Error("unexpected camera geometry");
    });
    const view = await render(<MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />);
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_capture_a11y"));
    });
    expect(view.getByTestId("math-scanner-preview").props.source).toEqual({ uri: "file:///shot.jpg" });
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_solve"));
    });
    const [frame] = shot.mock.calls[0]!;
    const [, cropFor] = jest.mocked(cropScanImage).mock.calls.at(-1)!;
    const sent = cropFor(MOCK_SIZES["file:///shot.jpg"]!);
    // What was aimed at, not the whole photo.
    for (const key of ["originX", "originY", "width", "height"] as const) {
      expect(Math.abs(sent[key] - frame[key])).toBeLessThanOrEqual(2);
    }
    expect(warn).toHaveBeenCalledWith("[scanner] could not cut the shot; showing the whole photo", "unexpected camera geometry");
    shot.mockRestore();
    warn.mockRestore();
  });

  it("retakes from the crop screen back to the live camera without sending", async () => {
    const onCaptured = jest.fn();
    const view = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={onCaptured} />,
    );
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_capture_a11y"));
    });
    await act(async () => {
      fireEvent.press(view.getByTestId("math-scanner-preview-retake"));
    });
    expect(view.queryByTestId("math-scanner-preview")).toBeNull();
    expect(view.getByTestId("math-scanner-shutter-ready")).toBeTruthy();
    expect(view.getByTestId("mock-live-scanner-camera")).toBeTruthy();
    expect(onCaptured).not.toHaveBeenCalled();
    expect(deletedFiles()).toEqual(expect.arrayContaining(["file:///shot.jpg", "file:///cropped.jpg"]));
  });

  it("steps back on Android Back: from the crop screen to the camera, then out", async () => {
    const onClose = jest.fn();
    const onCaptured = jest.fn();
    const view = await render(
      <MathEquationScanner visible onClose={onClose} onCaptured={onCaptured} />,
    );
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_capture_a11y"));
    });
    expect(view.getByTestId("math-scanner-preview")).toBeTruthy();

    // Back on the crop screen is Retake: the camera again, the scanner still open.
    await act(async () => {
      fireEvent(view.getByTestId("math-scanner-modal"), "requestClose");
    });
    expect(onClose).not.toHaveBeenCalled();
    expect(view.queryByTestId("math-scanner-preview")).toBeNull();
    expect(view.getByTestId("math-scanner-shutter-ready")).toBeTruthy();
    expect(onCaptured).not.toHaveBeenCalled();

    // Back on the camera closes the scanner.
    await act(async () => {
      fireEvent(view.getByTestId("math-scanner-modal"), "requestClose");
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("steps back the same way on VoiceOver's escape scrub, which the scanner's page answers as Back", async () => {
    const onClose = jest.fn();
    const view = await render(<MathEquationScanner visible onClose={onClose} onCaptured={jest.fn()} />);
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_capture_a11y"));
    });
    let failCut: (error: Error) => void = () => undefined;
    jest.mocked(cropScanImage).mockImplementationOnce(
      () => new Promise((_resolve, reject) => {
        failCut = reject;
      }),
    );
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_solve"));
    });
    const escape = () => fireEvent(view.getByTestId("full-screen-modal-page"), "accessibilityEscape");

    // While Solve cuts the shot the scrub does nothing, as Retake does nothing.
    await act(async () => escape());
    expect(view.getByTestId("math-scanner-preview")).toBeTruthy();
    expect(onClose).not.toHaveBeenCalled();

    // A failed cut leaves the crop screen up: now the scrub retakes, then closes.
    await act(async () => {
      failCut(new Error("no cut"));
    });
    await act(async () => escape());
    expect(view.queryByTestId("math-scanner-preview")).toBeNull();
    expect(onClose).not.toHaveBeenCalled();
    await act(async () => escape());
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("holds Back on the crop screen while Solve cuts the shot, as it holds Retake", async () => {
    const onClose = jest.fn();
    const onCaptured = jest.fn();
    const view = await render(
      <MathEquationScanner visible onClose={onClose} onCaptured={onCaptured} />,
    );
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_capture_a11y"));
    });
    let finishCut: (cut: { uri: string; width: number; height: number }) => void = () => undefined;
    jest.mocked(cropScanImage).mockImplementationOnce(
      () => new Promise((resolve) => {
        finishCut = resolve;
      }),
    );
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_solve"));
    });

    await act(async () => {
      fireEvent(view.getByTestId("math-scanner-modal"), "requestClose");
    });
    expect(onClose).not.toHaveBeenCalled();
    expect(view.getByTestId("math-scanner-preview")).toBeTruthy();

    await act(async () => {
      finishCut({ uri: "file:///solved.jpg", width: 320, height: 150 });
    });
    expect(onCaptured).toHaveBeenCalledWith(expect.objectContaining({ localUri: "file:///solved.jpg" }), "math");
  });
});

describe("imported math scanner photos", () => {
  beforeEach(() => {
    mockPermission.granted = true;
    mockPermission.canAskAgain = true;
    jest.spyOn(Dimensions, "get").mockReturnValue({ width: 390, height: 844, scale: 3, fontScale: 1 });
    jest.mocked(pickFromPhotoLibrary).mockResolvedValue({
      localUri: "file:///landscape.png", contentType: "image/png", fileName: "landscape.png", kind: "image",
    });
    jest.mocked(cropScanImage).mockClear();
    jest.mocked(deleteAsync).mockClear();
    mockScanImages();
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
    expect(cropScanImage).toHaveBeenCalledWith("file:///landscape.png", expect.any(Function));
    const [, cropFor] = jest.mocked(cropScanImage).mock.calls[0];
    expect(cropFor({ width: 1200, height: 700 })).toEqual({ originX: 0, originY: 0, width: 1200, height: 700 });
    expect(onCaptured).toHaveBeenCalledWith(
      expect.objectContaining({ localUri: "file:///cropped.jpg" }),
      "math",
    );
  });

  it.each(["math", "physics", "chemistry", "biology"])(
    "sends a picked %s photo with its tab's subject on Solve",
    async (subject) => {
      const onCaptured = jest.fn();
      const view = await render(
        <MathEquationScanner visible onClose={jest.fn()} onCaptured={onCaptured} />,
      );
      await act(async () => {
        fireEvent.press(view.getByTestId(`scanner-subject-${subject}`));
      });
      await act(async () => {
        fireEvent.press(view.getByLabelText("chat.math_scan_photos_a11y"));
      });
      expect(onCaptured).not.toHaveBeenCalled();
      await act(async () => {
        fireEvent.press(view.getByLabelText("chat.math_scan_solve"));
      });
      expect(onCaptured).toHaveBeenCalledTimes(1);
      expect(onCaptured).toHaveBeenCalledWith(
        expect.objectContaining({ localUri: "file:///cropped.jpg" }),
        subject,
      );
    },
  );

  it("moves the frame onto a photo's text once the phone has read it", async () => {
    jest.mocked(readTextLines).mockResolvedValueOnce([{ x: 0.3, y: 0.4, width: 0.4, height: 0.1 }]);
    const view = await render(<MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />);
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_photos_a11y"));
    });
    expect(readTextLines).toHaveBeenCalledWith("file:///landscape.png", expect.objectContaining({ width: 1200, height: 700 }));
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_solve"));
    });
    const [, cropFor] = jest.mocked(cropScanImage).mock.calls[0]!;
    const sent = cropFor({ width: 1200, height: 700 });
    // The text, with a margin, instead of the whole photo.
    expect(sent.width).toBeLessThan(1200 * 0.6);
    expect(sent.originX).toBeLessThanOrEqual(0.3 * 1200);
    expect(sent.originX + sent.width).toBeGreaterThanOrEqual(0.7 * 1200);
    expect(sent.originY).toBeLessThanOrEqual(0.4 * 700);
    expect(sent.originY + sent.height).toBeGreaterThanOrEqual(0.5 * 700);
  });

  it("keeps manual crop for imported photos", async () => {
    const view = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_photos_a11y"));
    });
    expect(view.getByTestId("math-scanner-preview").props.resizeMode).toBe("contain");
    expect(view.getByLabelText("chat.math_scan_frame_a11y")).toBeTruthy();
  });
});

describe("scanner sessions and scan files", () => {
  beforeEach(() => {
    jest.spyOn(Dimensions, "get").mockReturnValue({ width: 390, height: 844, scale: 3, fontScale: 1 });
    mockPermission.granted = true;
    mockTakePictureAsync.mockClear();
    jest.mocked(cropScanImage).mockClear();
    jest.mocked(deleteAsync).mockClear();
    mockScanImages();
    jest.mocked(pickFromPhotoLibrary).mockResolvedValue({
      localUri: "file:///landscape.png", contentType: "image/png", fileName: "landscape.png", kind: "image",
    });
  });

  function deferredPhoto() {
    let resolve: (photo: { uri: string }) => void = () => undefined;
    mockTakePictureAsync.mockImplementationOnce(
      () => new Promise<{ uri: string } | null>((done) => {
        resolve = done;
      }),
    );
    return () => resolve({ uri: "file:///shot.jpg" });
  }

  function scanner() {
    const all = {
      visible: true,
      onClose: jest.fn(),
      onCaptured: jest.fn(),
    };
    const element = (visible = true) => <MathEquationScanner {...all} visible={visible} />;
    return { all, element };
  }

  it.each(["biology", "math"])("drops a %s capture that lands after the scanner closed", async (subject) => {
    const finish = deferredPhoto();
    const { all, element } = scanner();
    const view = await render(element());
    await act(async () => {
      fireEvent.press(view.getByTestId(`scanner-subject-${subject}`));
    });
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_capture_a11y"));
    });
    await view.rerender(element(false));
    await act(async () => {
      finish();
    });
    expect(cropScanImage).not.toHaveBeenCalled();
    expect(all.onCaptured).not.toHaveBeenCalled();
    expect(deletedFiles()).toContain("file:///shot.jpg");
  });

  it("drops a crop that finishes after the scanner closed, and deletes it", async () => {
    let finishCrop: () => void = () => undefined;
    jest.mocked(cropScanImage).mockImplementationOnce(
      () => new Promise((done) => {
        finishCrop = () => done({ uri: "file:///cropped.jpg", width: 10, height: 10 });
      }),
    );
    const { all, element } = scanner();
    const view = await render(element());
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_capture_a11y"));
    });
    await view.rerender(element(false));
    await act(async () => {
      finishCrop();
    });
    expect(all.onCaptured).not.toHaveBeenCalled();
    expect(view.queryByTestId("math-scanner-preview")).toBeNull();
    expect(deletedFiles()).toEqual(expect.arrayContaining(["file:///shot.jpg", "file:///cropped.jpg"]));
  });

  it("sends with the subject the shot was taken with", async () => {
    const finish = deferredPhoto();
    const { all, element } = scanner();
    const view = await render(element());
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_capture_a11y"));
    });
    await act(async () => {
      fireEvent.press(view.getByTestId("scanner-subject-physics"));
    });
    await act(async () => {
      finish();
    });
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_solve"));
    });
    expect(all.onCaptured).toHaveBeenCalledWith(expect.anything(), "math");
  });

  it.each([
    ["math-scanner-preview-retake", ["file:///landscape.png"]],
    ["math-scanner-preview-solve", ["file:///landscape.png"]],
  ])("after %s deletes %j; only a sent crop is kept", async (action, deleted) => {
    const { element } = scanner();
    const view = await render(element());
    await act(async () => {
      fireEvent.press(view.getByTestId("math-scanner-photos"));
    });
    await act(async () => {
      fireEvent.press(view.getByTestId(action));
    });
    expect(deletedFiles().sort()).toEqual(deleted);
  });

  it("deletes every scan file when the scanner closes", async () => {
    const { element } = scanner();
    const view = await render(element());
    await act(async () => {
      fireEvent.press(view.getByTestId("math-scanner-photos"));
    });
    await view.rerender(element(false));
    expect(deletedFiles()).toEqual(["file:///landscape.png"]);
  });

  it("crops once when Solve is tapped twice", async () => {
    const { element } = scanner();
    const view = await render(element());
    await act(async () => {
      fireEvent.press(view.getByTestId("math-scanner-photos"));
    });
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_solve"));
      fireEvent.press(view.getByLabelText("chat.math_scan_solve"));
    });
    expect(cropScanImage).toHaveBeenCalledTimes(1);
  });
});
