import {
  forwardRef,
  useCallback,
  useImperativeHandle,
  useMemo,
  useRef,
} from "react";
import { StyleSheet, View } from "react-native";
import {
  Camera,
  CommonResolutions,
  useCameraDevice,
  useFrameOutput,
  usePhotoOutput,
} from "react-native-vision-camera";
import {
  useTextRecognition,
  type RegionOfInterest,
} from "react-native-vision-camera-mlkit";
import { scheduleOnRN } from "react-native-worklets";

import type { ScanRegion } from "@/lib/math/scannerRegion";

export type LiveScannerDetection = {
  hasText: boolean;
  stable: boolean;
  text: string;
};

export type LiveScannerCameraHandle = {
  takePictureAsync: () => Promise<{
    uri: string;
    width: number;
    height: number;
  } | null>;
};

type Props = {
  active: boolean;
  torchOn: boolean;
  zoom: number;
  scanRegion: ScanRegion;
  onReady: () => void;
  onError: () => void;
  onDetectionChange: (detection: LiveScannerDetection) => void;
};

const STABLE_FRAMES = 3;
const MAX_SCANNER_ZOOM = 6;
const MATH_SIGNAL = /[0-9=+\-*/^<>≤≥√∫π%()]/;
const MATH_WORD = /\b(?:sin|cos|tan|log|ln|sqrt|lim|dx|dy|area|solve|find)\b/i;

function normalizeLiveText(text: string): string {
  return text.replace(/\s+/g, " ").trim().toLowerCase();
}

function hasUsefulScannerText(text: string): boolean {
  const trimmed = text.trim();
  if (trimmed.length < 2) return false;
  return MATH_SIGNAL.test(trimmed) || MATH_WORD.test(trimmed) || /\d/.test(trimmed);
}

/**
 * Native VisionCamera preview + low-resolution ML Kit frame OCR.
 *
 * The live OCR is only a targeting signal. Recall still performs the final,
 * high-quality Mathpix/vision read after capture, so live frames never hit a
 * paid cloud OCR endpoint.
 */
export const LiveMathScannerCamera = forwardRef<LiveScannerCameraHandle, Props>(
  function LiveMathScannerCamera(
    {
      active,
      torchOn,
      zoom,
      scanRegion,
      onReady,
      onError,
      onDetectionChange,
    },
    ref,
  ) {
    const device = useCameraDevice("back");
    const photoOutput = usePhotoOutput({
      targetResolution: CommonResolutions.UHD_4_3,
      containerFormat: "jpeg",
      quality: 0.92,
      qualityPrioritization: "balanced",
    });
    const roi = useMemo<RegionOfInterest>(
      () => ({
        x: scanRegion.x,
        y: scanRegion.y,
        width: scanRegion.width,
        height: scanRegion.height,
        unit: "normalized",
      }),
      [scanRegion.height, scanRegion.width, scanRegion.x, scanRegion.y],
    );
    const { textRecognition } = useTextRecognition({
      language: "LATIN",
      roi,
      scaleFactor: 0.92,
    });
    const lastTextRef = useRef("");
    const stableCountRef = useRef(0);
    const lastDetectionKeyRef = useRef("");

    const publishFrameText = useCallback(
      (rawText: string) => {
        const normalized = normalizeLiveText(rawText);
        const hasText = hasUsefulScannerText(rawText);

        if (!hasText) {
          lastTextRef.current = "";
          stableCountRef.current = 0;
        } else if (normalized === lastTextRef.current) {
          stableCountRef.current += 1;
        } else {
          lastTextRef.current = normalized;
          stableCountRef.current = 1;
        }

        const stable = hasText && stableCountRef.current >= STABLE_FRAMES;
        const key = `${hasText ? 1 : 0}:${stable ? 1 : 0}:${normalized}`;
        if (key === lastDetectionKeyRef.current) return;
        lastDetectionKeyRef.current = key;
        onDetectionChange({ hasText, stable, text: rawText.trim() });
      },
      [onDetectionChange],
    );

    const frameOutput = useFrameOutput({
      targetResolution: CommonResolutions.VGA_16_9,
      pixelFormat: "yuv",
      onFrame(frame) {
        "worklet";
        try {
          const result = textRecognition(frame, { outputOrientation: "portrait" });
          scheduleOnRN(publishFrameText, result.text);
        } finally {
          frame.dispose();
        }
      },
    });

    const outputs = useMemo(
      () => [photoOutput, frameOutput],
      [frameOutput, photoOutput],
    );
    const constraints = useMemo(() => [{ fps: 12 }], []);

    const cameraZoom = useMemo(() => {
      if (!device) return 1;
      const neutral = Math.max(device.minZoom, device.neutralZoom);
      const max = Math.max(neutral, Math.min(device.maxZoom, MAX_SCANNER_ZOOM));
      return neutral + Math.min(1, Math.max(0, zoom)) * (max - neutral);
    }, [device, zoom]);

    useImperativeHandle(
      ref,
      () => ({
        async takePictureAsync() {
          if (!device || !active) return null;
          const photo = await photoOutput.capturePhotoToFile(
            {
              flashMode: "off",
              enableShutterSound: true,
              enableDistortionCorrection: true,
            },
            {},
          );
          return {
            uri: `file://${photo.filePath}`,
            width: photo.width,
            height: photo.height,
          };
        },
      }),
      [active, device, photoOutput],
    );

    if (!device) {
      return <View style={StyleSheet.absoluteFill} />;
    }

    return (
      <Camera
        style={StyleSheet.absoluteFill}
        device={device}
        isActive={active}
        outputs={outputs}
        constraints={constraints}
        orientationSource="interface"
        zoom={cameraZoom}
        torchMode={torchOn && device.hasTorch ? "on" : "off"}
        enableSmoothAutoFocus
        onStarted={onReady}
        onError={onError}
      />
    );
  },
);
