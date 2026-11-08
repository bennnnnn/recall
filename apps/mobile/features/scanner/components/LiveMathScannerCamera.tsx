import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { StyleSheet, View } from "react-native";

import { nativeScannerLinked } from "@/features/scanner/model/nativeCamera";
import type {
  LiveScannerCameraHandle,
  LiveScannerCameraProps,
  LiveScannerDetection,
} from "@/features/scanner/components/LiveMathScannerCameraNative";

export type { LiveScannerCameraHandle, LiveScannerDetection };

type NativeCamera =
  typeof import("@/features/scanner/components/LiveMathScannerCameraNative").LiveMathScannerCameraNative;

type Props = LiveScannerCameraProps & {
  /** The native camera is not in this build (Expo Go, or a dev client built before it). */
  onUnavailable: () => void;
};

/**
 * Loads the live scanner only after this view mounts. A static import pulls in
 * VisionCamera and Nitro, which crashes chat in Expo Go and in a dev client
 * built before that camera library existed. The build is asked first
 * (`nativeScannerLinked`): where the native camera or ML Kit is missing, the
 * scanner says the live camera is not in this build instead of loading it.
 * A load that fails anyway, or resolves without the camera (Metro resolves a
 * module that threw while loading to an empty one), says the same.
 */
export const LiveMathScannerCamera = forwardRef<LiveScannerCameraHandle, Props>(
  function LiveMathScannerCamera({ onUnavailable, ...props }, ref) {
    const nativeRef = useRef<LiveScannerCameraHandle>(null);
    const [Native, setNative] = useState<NativeCamera | null>(null);
    const onUnavailableRef = useRef(onUnavailable);
    useEffect(() => {
      onUnavailableRef.current = onUnavailable;
    }, [onUnavailable]);

    useImperativeHandle(
      ref,
      () => ({
        async takePictureAsync() {
          return (await nativeRef.current?.takePictureAsync()) ?? null;
        },
        focusAt(point) {
          nativeRef.current?.focusAt(point);
        },
      }),
      [],
    );

    useEffect(() => {
      let cancelled = false;
      void loadNativeCamera().then((camera) => {
        if (cancelled) return;
        if (camera) setNative(() => camera);
        else onUnavailableRef.current();
      });
      return () => {
        cancelled = true;
      };
    }, []);

    if (!Native) return <View style={StyleSheet.absoluteFill} />;

    return <Native ref={nativeRef} {...props} />;
  },
);

/** The native camera component, or null when this build cannot load it. */
async function loadNativeCamera(): Promise<NativeCamera | null> {
  try {
    if (!(await nativeScannerLinked())) return null;
    const mod = await import("@/features/scanner/components/LiveMathScannerCameraNative");
    return mod?.LiveMathScannerCameraNative ?? null;
  } catch {
    // The camera's modules threw while loading: the same as a build without them.
    return null;
  }
}
