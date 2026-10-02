import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { StyleSheet, TurboModuleRegistry, View } from "react-native";
import { CameraView } from "expo-camera";

import type { ScanRegion } from "@/lib/math/scannerRegion";
import type {
  LiveScannerCameraHandle,
  LiveScannerDetection,
} from "@/components/mathScanner/LiveMathScannerCameraNative";

export type { LiveScannerCameraHandle, LiveScannerDetection };

type NativeCamera =
  typeof import("@/components/mathScanner/LiveMathScannerCameraNative").LiveMathScannerCameraNative;

type Props = {
  active: boolean;
  torchOn: boolean;
  zoom: number;
  scanRegion: ScanRegion;
  onReady: () => void;
  onError: () => void;
  onDetectionChange: (detection: LiveScannerDetection) => void;
};

/**
 * VisionCamera throws while its module is evaluated when Nitro is missing.
 * `import().catch` still paints that as an uncaught redbox, so the native
 * file must not be loaded at all. Expo Go then uses `expo-camera`.
 */
function nitroModulesPresent(): boolean {
  try {
    return TurboModuleRegistry.get("NitroModules") != null;
  } catch {
    return false;
  }
}

const ExpoScannerCamera = forwardRef<LiveScannerCameraHandle, Props>(
  function ExpoScannerCamera({ active, torchOn, zoom, onReady, onError }, ref) {
    const cameraRef = useRef<CameraView>(null);

    useImperativeHandle(
      ref,
      () => ({
        async takePictureAsync() {
          const photo = await cameraRef.current?.takePictureAsync({
            quality: 0.92,
            shutterSound: true,
          });
          if (!photo?.uri) return null;
          return { uri: photo.uri, width: photo.width, height: photo.height };
        },
      }),
      [],
    );

    return (
      <CameraView
        ref={cameraRef}
        style={StyleSheet.absoluteFill}
        facing="back"
        mode="picture"
        active={active}
        zoom={zoom}
        enableTorch={torchOn}
        animateShutter={false}
        onCameraReady={onReady}
        onMountError={onError}
      />
    );
  },
);

/**
 * Loads the live scanner only after this view mounts, and only when Nitro is
 * in the binary. A static import crashes chat in Expo Go.
 */
export const LiveMathScannerCamera = forwardRef<LiveScannerCameraHandle, Props>(
  function LiveMathScannerCamera(props, ref) {
    const nativeRef = useRef<LiveScannerCameraHandle>(null);
    const onErrorRef = useRef(props.onError);
    const [Native, setNative] = useState<NativeCamera | null>(null);
    const useExpoCamera = useRef(!nitroModulesPresent()).current;

    onErrorRef.current = props.onError;

    useImperativeHandle(
      ref,
      () => ({
        async takePictureAsync() {
          return (await nativeRef.current?.takePictureAsync()) ?? null;
        },
      }),
      [],
    );

    useEffect(() => {
      if (useExpoCamera) return;
      let cancelled = false;
      import("./LiveMathScannerCameraNative")
        .then((mod) => {
          if (!cancelled) setNative(() => mod.LiveMathScannerCameraNative);
        })
        .catch(() => {
          if (!cancelled) onErrorRef.current();
        });
      return () => {
        cancelled = true;
      };
    }, [useExpoCamera]);

    if (useExpoCamera) return <ExpoScannerCamera ref={nativeRef} {...props} />;
    if (!Native) return <View style={StyleSheet.absoluteFill} />;
    return <Native ref={nativeRef} {...props} />;
  },
);
