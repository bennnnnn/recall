import React from "react";
import { Dimensions, Image } from "react-native";
import * as ImageManipulator from "expo-image-manipulator";

import { pickImageDocument } from "@/features/attachments/model/attachments";
import { act, fireEvent, render, within } from "@testing-library/react-native";

import { MathEquationScanner } from "@/components/MathEquationScanner";
import { selection } from "@/lib/haptics";
import { playScannerSwitchCue } from "@/lib/scanner/switchCue";
import { lightTheme as mockLightTheme } from "@/lib/theme";

const mockTakePictureAsync = jest.fn(async () => ({
  uri: "file:///shot.jpg",
  width: 800,
  height: 1200,
}));
const mockPermission = { granted: true, canAskAgain: true };

jest.mock("expo-camera", () => ({
  useCameraPermissions: () => [mockPermission, jest.fn()],
}));

jest.mock("@/components/mathScanner/LiveMathScannerCamera", () => {
  const ReactNative = jest.requireActual<typeof import("react")>("react");
  const { View } = jest.requireActual<typeof import("react-native")>("react-native");
  const LiveMathScannerCamera = ReactNative.forwardRef(
    (
      props: {
        onReady?: () => void;
        onDetectionChange?: (detection: {
          hasText: boolean;
          stable: boolean;
          text: string;
        }) => void;
      },
      ref: unknown,
    ) => {
      ReactNative.useImperativeHandle(ref, () => ({ takePictureAsync: mockTakePictureAsync }));
      ReactNative.useEffect(() => {
        let cancelled = false;
        queueMicrotask(() => {
          if (!cancelled) props.onReady?.();
        });
        return () => {
          cancelled = true;
        };
      }, [props.onReady]);
      return ReactNative.createElement(View, {
        testID: "mock-live-scanner-camera",
        onDetectionChange: props.onDetectionChange,
      });
    },
  );
  LiveMathScannerCamera.displayName = "LiveMathScannerCamera";
  return { LiveMathScannerCamera };
});

jest.mock("expo-image-manipulator", () => ({
  SaveFormat: { JPEG: "jpeg" },
  manipulateAsync: jest.fn(async () => ({ uri: "file:///cropped.jpg" })),
}));

jest.mock("expo-file-system", () => ({
  File: class {
    exists = true;
    delete = jest.fn();
  },
}));

jest.mock("expo-linear-gradient", () => {
  return { LinearGradient: "LinearGradient" };
});

jest.mock("@/lib/lastPhotoThumbnail", () => ({
  loadLastPhotoUri: jest.fn(async () => null),
  useLastPhotoThumb: () => null,
}));

jest.mock("@/features/attachments/model/attachments", () => ({
  pickImageDocument: jest.fn(async () => null),
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
jest.mock("@/lib/scanner/switchCue", () => ({
  playScannerSwitchCue: jest.fn(async () => undefined),
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
    jest.mocked(ImageManipulator.manipulateAsync).mockClear();
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
    expect(getByTestId("scanner-subject-guide-math")).toBeTruthy();
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

  it("switches to physics with one directional sound and haptic cue", async () => {
    const { getByTestId } = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    await act(async () => {
      fireEvent.press(getByTestId("scanner-subject-physics"));
    });
    expect(selection).toHaveBeenCalled();
    expect(playScannerSwitchCue).toHaveBeenCalledWith(1);
    expect(getByTestId("scanner-subject-guide-physics")).toBeTruthy();
  });

  it("reads a chemistry photo through the chemistry reader, not as math", async () => {
    const onReadScan = jest.fn(async () => null);
    const { getByTestId, getByLabelText } = await render(
      <MathEquationScanner
        visible
        onClose={jest.fn()}
        onCaptured={jest.fn()}
        onReadScan={onReadScan}
        onSolveReading={jest.fn()}
      />,
    );
    await act(async () => {
      fireEvent.press(getByTestId("scanner-subject-chemistry"));
    });
    await act(async () => {
      fireEvent.press(getByLabelText("chat.math_scan_capture_a11y"));
    });
    expect(onReadScan).toHaveBeenCalledTimes(1);
    expect(onReadScan).toHaveBeenCalledWith(
      expect.objectContaining({ localUri: "file:///cropped.jpg" }),
      "chemistry",
      expect.anything(),
    );
  });

  it("shows the biology guide when biology is selected", async () => {
    const { getByTestId } = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={jest.fn()} />,
    );
    await act(async () => {
      fireEvent.press(getByTestId("scanner-subject-biology"));
    });
    expect(getByTestId("scanner-subject-guide-biology")).toBeTruthy();
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

  it("crops the live camera frame immediately instead of requiring a second Solve tap", async () => {
    const onCaptured = jest.fn();
    const { getByTestId, getByLabelText, queryByTestId } = await render(
      <MathEquationScanner visible onClose={jest.fn()} onCaptured={onCaptured} />,
    );
    await act(async () => {
      fireEvent.press(getByLabelText("chat.math_scan_capture_a11y"));
    });
    expect(mockTakePictureAsync).toHaveBeenCalledTimes(1);
    expect(ImageManipulator.manipulateAsync).toHaveBeenCalledWith(
      "file:///shot.jpg",
      [{ crop: expect.objectContaining({ width: expect.any(Number), height: expect.any(Number) }) }],
      { compress: 0.9, format: "jpeg" },
    );
    expect(onCaptured).toHaveBeenCalledWith(
      expect.objectContaining({ localUri: "file:///cropped.jpg" }),
      "math",
    );
    expect(getByTestId("math-scanner-camera")).toBeTruthy();
    expect(queryByTestId("math-scanner-preview")).toBeNull();
  });

  it("starts math OCR review immediately after a camera capture", async () => {
    const read = jest.fn(async () => ({
      reading: "2x + 3 = 7",
      uncertain: false,
      source: "mathpix" as const,
    }));
    const view = await render(
      <MathEquationScanner
        visible
        onClose={jest.fn()}
        onCaptured={jest.fn()}
        onReadScan={read}
        onSolveReading={jest.fn()}
      />,
    );
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_capture_a11y"));
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(read).toHaveBeenCalledWith(
      expect.objectContaining({ localUri: "file:///cropped.jpg" }),
      "math",
      expect.anything(),
    );
    expect(view.getByTestId("math-scan-review")).toBeTruthy();
    expect(view.queryByTestId("math-scanner-preview")).toBeNull();
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
    jest.mocked(pickImageDocument).mockResolvedValue({
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
    expect(onCaptured).toHaveBeenCalledWith(
      expect.objectContaining({ localUri: "file:///cropped.jpg" }),
      "math",
    );
  });

  async function cropForReview(
    read: jest.Mock,
    extra: Partial<React.ComponentProps<typeof MathEquationScanner>> = {},
  ) {
    const onCaptured = jest.fn();
    const onSolveReading = jest.fn();
    const view = await render(
      <MathEquationScanner
        visible
        onClose={jest.fn()}
        onCaptured={onCaptured}
        onReadScan={read}
        onSolveReading={onSolveReading}
        {...extra}
      />,
    );
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_photos_a11y"));
    });
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_solve"));
    });
    return { ...view, onCaptured, onSolveReading };
  }

  it("reads a math crop back and solves the confirmed text", async () => {
    const read = jest.fn(async () => ({ reading: "2x + 3 = 7", uncertain: false, source: "mathpix" }));
    const view = await cropForReview(read);
    expect(read).toHaveBeenCalledWith(
      expect.objectContaining({ localUri: "file:///cropped.jpg" }),
      "math",
      expect.anything(),
    );
    const review = within(view.getByTestId("math-scan-review"));
    await act(async () => {
      fireEvent.changeText(review.getByTestId("math-scan-reading"), "2x + 3 = 11");
    });
    await act(async () => {
      fireEvent.press(review.getByText("chat.math_scan_solve"));
    });
    expect(view.onSolveReading).toHaveBeenCalledWith("2x + 3 = 11", "math");
    expect(view.onCaptured).not.toHaveBeenCalled();
    expect(view.queryByTestId("math-scanner-shutter")).toBeNull();
    expect(view.queryByTestId("math-scanner-preview-retake")).toBeNull();
    expect(view.queryByTestId("math-scanner-preview-solve")).toBeNull();
    expect(view.getByTestId("math-scanner-close")).toBeTruthy();
  });

  it("sends the photo with the reading the student checked", async () => {
    const read = jest.fn(async () => ({ reading: "x^2 = 9", uncertain: true, source: "vision" }));
    const view = await cropForReview(read);
    const review = within(view.getByTestId("math-scan-review"));
    expect(review.getByText("chat.math_scan_uncertain")).toBeTruthy();
    await act(async () => {
      fireEvent.press(review.getByText("chat.math_scan_send_photo"));
    });
    expect(view.onCaptured).toHaveBeenCalledWith(
      expect.objectContaining({ localUri: "file:///cropped.jpg" }),
      "math",
      "x^2 = 9",
    );
  });

  it("shows a rate limit instead of the generic read failure", async () => {
    const read = jest.fn(async () => ({ error: "Too many scans in a row. Try again in a few minutes." }));
    const view = await cropForReview(read);
    expect(
      within(view.getByTestId("math-scan-review")).getByText(
        "Too many scans in a row. Try again in a few minutes.",
      ),
    ).toBeTruthy();
    expect(view.queryByText("chat.math_scan_read_failed")).toBeNull();
  });

  it("does not send a ready reading the student wiped", async () => {
    const read = jest.fn(async () => ({ reading: "2x = 4", uncertain: false, source: "mathpix" as const }));
    const view = await cropForReview(read);
    const review = within(view.getByTestId("math-scan-review"));
    await act(async () => {
      fireEvent.changeText(review.getByTestId("math-scan-reading"), "   ");
    });
    const send = review.getByText("chat.math_scan_send_photo");
    expect(send).toBeDisabled();
    await act(async () => {
      fireEvent.press(send);
    });
    expect(view.onCaptured).not.toHaveBeenCalled();
  });

  it("falls back to the photo when the read fails", async () => {
    const read = jest.fn(async () => null);
    const view = await cropForReview(read);
    const review = within(view.getByTestId("math-scan-review"));
    expect(review.getByText("chat.math_scan_read_failed")).toBeTruthy();
    await act(async () => {
      fireEvent.press(review.getByText("chat.math_scan_send_photo"));
    });
    expect(view.onCaptured).toHaveBeenCalledWith(
      expect.objectContaining({ localUri: "file:///cropped.jpg" }),
      "math",
      undefined,
    );
  });

  it("reads a chemistry crop as text and solves that text alone", async () => {
    const onReadScan = jest.fn(async () => ({
      reading: "Find the molar mass of H2O",
      uncertain: false,
      source: "vision" as const,
    }));
    const onCaptured = jest.fn();
    const onSolveReading = jest.fn();
    const view = await render(
      <MathEquationScanner
        visible
        onClose={jest.fn()}
        onCaptured={onCaptured}
        onReadScan={onReadScan}
        onSolveReading={onSolveReading}
      />,
    );
    await act(async () => {
      fireEvent.press(view.getByTestId("scanner-subject-chemistry"));
    });
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_photos_a11y"));
    });
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_solve"));
    });
    expect(onReadScan).toHaveBeenCalledTimes(1);
    expect(onReadScan).toHaveBeenCalledWith(expect.anything(), "chemistry", expect.anything());
    const review = within(view.getByTestId("math-scan-review"));
    await act(async () => {
      fireEvent.press(review.getByText("chat.math_scan_solve"));
    });
    expect(onSolveReading).toHaveBeenCalledWith("Find the molar mass of H2O", "chemistry");
    expect(onCaptured).not.toHaveBeenCalled();
  });

  it("sends the chemistry photo with the reading the student checked", async () => {
    const onCaptured = jest.fn();
    const view = await render(
      <MathEquationScanner
        visible
        onClose={jest.fn()}
        onCaptured={onCaptured}
        onReadScan={jest.fn(async () => ({
          reading: "Find the molar mass of H2O",
          uncertain: false,
          source: "vision" as const,
        }))}
        onSolveReading={jest.fn()}
      />,
    );
    await act(async () => {
      fireEvent.press(view.getByTestId("scanner-subject-chemistry"));
    });
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_photos_a11y"));
    });
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_solve"));
    });
    const review = within(view.getByTestId("math-scan-review"));
    await act(async () => {
      fireEvent.press(review.getByText("chat.math_scan_send_photo"));
    });
    expect(onCaptured).toHaveBeenCalledWith(
      expect.objectContaining({ localUri: "file:///cropped.jpg" }),
      "chemistry",
      "Find the molar mass of H2O",
    );
  });

  it("sends the chemistry photo when the read fails", async () => {
    const onCaptured = jest.fn();
    const view = await render(
      <MathEquationScanner
        visible
        onClose={jest.fn()}
        onCaptured={onCaptured}
        onReadScan={jest.fn(async () => null)}
        onSolveReading={jest.fn()}
      />,
    );
    await act(async () => {
      fireEvent.press(view.getByTestId("scanner-subject-chemistry"));
    });
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_photos_a11y"));
    });
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_solve"));
    });
    const review = within(view.getByTestId("math-scan-review"));
    expect(review.getByText("chat.math_scan_read_failed")).toBeTruthy();
    await act(async () => {
      fireEvent.press(review.getByText("chat.math_scan_send_photo"));
    });
    expect(onCaptured).toHaveBeenCalledTimes(1);
    expect(onCaptured).toHaveBeenCalledWith(
      expect.objectContaining({ localUri: "file:///cropped.jpg" }),
      "chemistry",
      undefined,
    );
  });

  it("retakes from the review back to the camera", async () => {
    const read = jest.fn(async () => ({ reading: "2x = 4", uncertain: false, source: "mathpix" }));
    const view = await cropForReview(read);
    await act(async () => {
      fireEvent.press(within(view.getByTestId("math-scan-review")).getByText("chat.math_scan_retake"));
    });
    expect(view.queryByTestId("math-scan-review")).toBeNull();
    expect(view.queryByTestId("math-scanner-preview")).toBeNull();
    expect(view.onCaptured).not.toHaveBeenCalled();
  });

  async function scanSubject(subject: string, read: jest.Mock) {
    const onCaptured = jest.fn();
    const onSolveReading = jest.fn();
    const view = await render(
      <MathEquationScanner
        visible
        onClose={jest.fn()}
        onCaptured={onCaptured}
        onReadScan={read}
        onSolveReading={onSolveReading}
      />,
    );
    await act(async () => {
      fireEvent.press(view.getByTestId(`scanner-subject-${subject}`));
    });
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_photos_a11y"));
    });
    await act(async () => {
      fireEvent.press(view.getByLabelText("chat.math_scan_solve"));
    });
    return { ...view, onCaptured, onSolveReading };
  }

  const PHYSICS_READING = "A ball is dropped from 80 m. Find its speed just before it hits the ground.";

  it("reads a physics crop back and solves the confirmed text", async () => {
    const read = jest.fn(async () => ({ reading: PHYSICS_READING, uncertain: false, source: "vision" }));
    const view = await scanSubject("physics", read);
    expect(read).toHaveBeenCalledWith(expect.anything(), "physics", expect.anything());
    const review = within(view.getByTestId("math-scan-review"));
    await act(async () => {
      fireEvent.press(review.getByText("chat.math_scan_solve"));
    });
    expect(view.onSolveReading).toHaveBeenCalledWith(PHYSICS_READING, "physics");
    expect(view.onCaptured).not.toHaveBeenCalled();
  });

  it("sends the physics photo with the reading the student checked", async () => {
    const read = jest.fn(async () => ({ reading: PHYSICS_READING, uncertain: false, source: "vision" }));
    const view = await scanSubject("physics", read);
    await act(async () => {
      fireEvent.press(within(view.getByTestId("math-scan-review")).getByText("chat.math_scan_send_photo"));
    });
    expect(view.onCaptured).toHaveBeenCalledWith(
      expect.objectContaining({ localUri: "file:///cropped.jpg" }),
      "physics",
      PHYSICS_READING,
    );
  });

  it("sends biology photos straight through without a read", async () => {
    const read = jest.fn(async () => ({ reading: "cell", uncertain: false, source: "vision" }));
    const view = await scanSubject("biology", read);
    expect(read).not.toHaveBeenCalled();
    expect(view.onCaptured).toHaveBeenCalledWith(
      expect.objectContaining({ localUri: "file:///cropped.jpg" }),
      "biology",
    );
  });

  it("keeps manual crop for imported photos while camera captures use the live frame", async () => {
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
