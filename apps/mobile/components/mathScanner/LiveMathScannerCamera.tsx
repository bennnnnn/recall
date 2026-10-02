import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { StyleSheet, View } from "react-native";

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
 * Loads the live scanner only after this view mounts. A static import pulls in
 * VisionCamera and Nitro, which crashes chat in Expo Go and in a dev client
 * built before that camera library existed.
 */
export const LiveMathScannerCamera = forwardRef<LiveScannerCameraHandle, Props>(
  function LiveMathScannerCamera(props, ref) {
    const nativeRef = useRef<LiveScannerCameraHandle>(null);
    const [Native, setNative] = useState<NativeCamera | null>(null);

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
      let cancelled = false;
      import("./LiveMathScannerCameraNative")
        .then((mod) => {
          if (!cancelled) setNative(() => mod.LiveMathScannerCameraNative);
        })
        .catch(() => {
          if (!cancelled) {
            setNative(null);
            props.onError();
          }
        });
      return () => {
        cancelled = true;
      };
    }, [props.onError]);

    if (!Native) return <View style={StyleSheet.absoluteFill} />;

    return <Native ref={nativeRef} {...props} />;
  },
);
