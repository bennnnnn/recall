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
import { hasUsefulScannerText, normalizeLiveText } from "@/lib/scanner/liveText";

export type LiveScannerDetection = {
  hasText: boolean;
  stable: boolean;
  text: string;
};

export type LiveScannerCameraHandle = {
  takePictureAsync: () => Promise<{
    uri: string;
    width?: number;
    height?: number;
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

/**
 * Native VisionCamera preview + low-resolution ML Kit frame OCR.
 *
 * The live OCR is only a targeting signal. Recall still performs the final,
 * high-quality Mathpix/vision read after capture, so live frames never hit a
 * paid cloud OCR endpoint.
 */
export const LiveMathScannerCameraNative = forwardRef<LiveScannerCameraHandle, Props>(
  function LiveMathScannerCameraNative(
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
      dropFramesWhileBusy: true,
      onFrameDropped: () => undefined,
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
    const constraints = useMemo(() => [{ fps: 30 }], []);

    const cameraZoom = useMemo(() => {
      if (!device) return 1;
      const neutral = Math.min(device.maxZoom, Math.max(device.minZoom, 1));
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
              enableDistortionCorrection: device.supportsDistortionCorrection,
            },
            {},
          );
          return {
            uri: `file://${photo.filePath}`,
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
