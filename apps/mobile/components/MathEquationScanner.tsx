import { useCallback, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as ImageManipulator from "expo-image-manipulator";
import { Ionicons } from "@expo/vector-icons";
import { Gesture, GestureDetector, GestureHandlerRootView } from "react-native-gesture-handler";
import { runOnJS } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import type { PendingAttachment } from "@/lib/attachments";
import {
  clampScanRegion,
  defaultScanRegion,
  regionToImageCrop,
  scaleScanRegion,
  translateScanRegion,
  type ScanRegion,
} from "@/lib/mathScannerRegion";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  visible: boolean;
  onClose: () => void;
  onCaptured: (pending: PendingAttachment) => void;
};

/**
 * In-app equation scanner: live camera with a free-form rectangular crop
 * guide. Drag to move it, pinch to resize it — capture crops only that
 * rectangle for OCR. A rectangle (not a fixed full-width band) fits a word
 * problem, a multi-line system, or a small diagram, not just one typed
 * equation line.
 */
export function MathEquationScanner({ visible, onClose, onCaptured }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { width: windowWidth, height: windowHeight } = useWindowDimensions();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [region, setRegion] = useState<ScanRegion>(defaultScanRegion());
  const regionRef = useRef(region);
  regionRef.current = region;
  const pinchBaseRef = useRef(region);
  const panBaseRef = useRef(region);

  const beginPinch = useCallback(() => {
    pinchBaseRef.current = regionRef.current;
  }, []);
  const applyPinchScale = useCallback((scale: number) => {
    setRegion(scaleScanRegion(pinchBaseRef.current, scale));
  }, []);

  const beginPan = useCallback(() => {
    panBaseRef.current = regionRef.current;
  }, []);
  const applyPanDelta = useCallback(
    (dxRatio: number, dyRatio: number) => {
      setRegion(translateScanRegion(panBaseRef.current, dxRatio, dyRatio));
    },
    [],
  );

  const pinchGesture = useMemo(
    () =>
      Gesture.Pinch()
        .onBegin(() => {
          runOnJS(beginPinch)();
        })
        .onUpdate((e) => {
          runOnJS(applyPinchScale)(e.scale);
        }),
    [applyPinchScale, beginPinch],
  );

  // maxPointers(1) is the fix for "pinch moves instead of resizes": without
  // it the Pan tracks the 2-finger pinch centroid and translates the region,
  // so the user sees movement (not a resize). Restrict Pan to one finger so a
  // 2-finger gesture goes to Pinch alone.
  const panGesture = useMemo(
    () =>
      Gesture.Pan()
        .maxPointers(1)
        .onBegin(() => {
          runOnJS(beginPan)();
        })
        .onUpdate((e) => {
          runOnJS(applyPanDelta)(e.translationX / windowWidth, e.translationY / windowHeight);
        }),
    [applyPanDelta, beginPan, windowWidth, windowHeight],
  );

  const regionGesture = useMemo(
    () => Gesture.Simultaneous(panGesture, pinchGesture),
    [panGesture, pinchGesture],
  );

  const regionLeft = Math.round(region.x * windowWidth);
  const regionTop = Math.round(region.y * windowHeight);
  const regionWidth = Math.round(region.width * windowWidth);
  const regionHeight = Math.round(region.height * windowHeight);
  const regionRight = regionLeft + regionWidth;
  const regionBottom = regionTop + regionHeight;

  const capture = useCallback(async () => {
    if (!cameraRef.current || busy) return;
    setBusy(true);
    setError(null);
    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.9,
        shutterSound: false,
      });
      if (!photo?.uri) {
        setError(t("chat.math_scan_failed"));
        return;
      }

      const imageWidth = photo.width ?? 0;
      const imageHeight = photo.height ?? 0;
      if (!imageWidth || !imageHeight) {
        // Fallback: use the full photo if dimensions are missing.
        onCaptured({
          localUri: photo.uri,
          contentType: "image/jpeg",
          fileName: `math-scan-${Date.now()}.jpg`,
          kind: "image",
        });
        onClose();
        return;
      }

      // CameraView uses cover-style fill; regionToImageCrop maps the
      // on-screen rectangle into image pixel coordinates assuming the
      // preview covers the full window edge-to-edge.
      const crop = regionToImageCrop(
        regionRef.current,
        imageWidth,
        imageHeight,
        windowWidth,
        windowHeight,
      );
      const result = await ImageManipulator.manipulateAsync(
        photo.uri,
        [{ crop }],
        { compress: 0.9, format: ImageManipulator.SaveFormat.JPEG },
      );

      onCaptured({
        localUri: result.uri,
        contentType: "image/jpeg",
        fileName: `math-scan-${Date.now()}.jpg`,
        kind: "image",
      });
      onClose();
    } catch {
      setError(t("chat.math_scan_failed"));
    } finally {
      setBusy(false);
    }
  }, [busy, onCaptured, onClose, t, windowWidth, windowHeight]);

  const resetRegion = useCallback(() => {
    setRegion(clampScanRegion(defaultScanRegion()));
  }, []);

  const cameraLayer = !permission ? (
    <View style={s.center}>
      <ActivityIndicator color={theme.onPrimary} />
    </View>
  ) : !permission.granted ? (
    <View style={s.center}>
      <Text style={s.permissionText}>{t("chat.math_scan_permission")}</Text>
      <Pressable style={s.permissionBtn} onPress={() => void requestPermission()}>
        <Text style={s.permissionBtnText}>{t("chat.math_scan_allow_camera")}</Text>
      </Pressable>
    </View>
  ) : (
    <>
      <CameraView ref={cameraRef} style={StyleSheet.absoluteFill} facing="back" mode="picture" />
      {/* 4-piece frame mask around the clear region — top/bottom span the
          full width, left/right only span the region's own row. */}
      <View style={s.maskLayer} pointerEvents="none">
        <View style={[s.mask, { top: 0, left: 0, right: 0, height: regionTop }]} />
        <View
          style={[s.mask, { top: regionBottom, left: 0, right: 0, bottom: 0 }]}
        />
        <View
          style={[s.mask, { top: regionTop, left: 0, width: regionLeft, height: regionHeight }]}
        />
        <View
          style={[
            s.mask,
            { top: regionTop, left: regionRight, right: 0, height: regionHeight },
          ]}
        />
      </View>
      <GestureDetector gesture={regionGesture}>
        <View
          style={[
            s.region,
            { left: regionLeft, top: regionTop, width: regionWidth, height: regionHeight },
          ]}
          collapsable={false}
        >
          <View style={s.cornerTL} />
          <View style={s.cornerTR} />
          <View style={s.cornerBL} />
          <View style={s.cornerBR} />
        </View>
      </GestureDetector>
    </>
  );

  // Overlay controls render AFTER the camera/gesture layer so they are above
  // it in tree order (and have a higher zIndex). Earlier the close button was
  // a sibling rendered BEFORE the CameraView (absoluteFill) — the camera layer
  // could cover it and swallow taps.
  const overlay = (
    <>
      <Pressable
        style={[s.close, { top: insets.top + 8 }]}
        onPress={onClose}
        hitSlop={12}
        accessibilityRole="button"
        accessibilityLabel={t("common.close")}
      >
        <Ionicons name="close" size={28} color="#fff" />
      </Pressable>
      <Pressable
        style={[s.resetBtn, { top: insets.top + 8 }]}
        onPress={resetRegion}
        hitSlop={10}
        accessibilityRole="button"
        accessibilityLabel={t("chat.math_scan_reset_a11y")}
      >
        <Ionicons name="scan-outline" size={20} color="#fff" />
      </Pressable>
      <View style={[s.hintWrap, { top: insets.top + 56 }]}>
        <Text style={s.hint}>{t("chat.math_scan_hint")}</Text>
      </View>
      {error ? <Text style={s.error}>{error}</Text> : null}
      <View style={[s.controls, { paddingBottom: Math.max(insets.bottom, 16) + 12 }]}>
        <Pressable
          style={s.shutter}
          onPress={() => void capture()}
          disabled={busy}
          accessibilityRole="button"
          accessibilityLabel={t("chat.math_scan_capture_a11y")}
        >
          {busy ? (
            <ActivityIndicator color={theme.text} />
          ) : (
            <View style={s.shutterInner} />
          )}
        </Pressable>
      </View>
    </>
  );

  if (!visible) return null;

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <GestureHandlerRootView style={s.root}>
        <View style={s.cameraLayer}>{cameraLayer}</View>
        <View style={s.overlayLayer} pointerEvents="box-none">
          {overlay}
        </View>
      </GestureHandlerRootView>
    </Modal>
  );
}

function makeStyles(theme: Theme) {
  const corner = {
    position: "absolute" as const,
    width: 24,
    height: 24,
    borderColor: theme.primary,
  };
  return StyleSheet.create({
    root: {
      flex: 1,
      backgroundColor: "#000",
    },
    // Camera + crop gesture sit in their own layer below the overlay controls.
    cameraLayer: {
      ...StyleSheet.absoluteFill,
      zIndex: 1,
    },
    // Overlay (close, reset, hint, shutter) renders above the camera so taps
    // always reach the buttons. pointerEvents="box-none" lets the crop
    // gesture underneath keep receiving touches in the empty areas.
    overlayLayer: {
      ...StyleSheet.absoluteFill,
      zIndex: 30,
    },
    close: {
      position: "absolute",
      left: 16,
      width: 40,
      height: 40,
      borderRadius: 20,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: "rgba(0,0,0,0.55)",
    },
    resetBtn: {
      position: "absolute",
      right: 16,
      width: 40,
      height: 40,
      borderRadius: 20,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: "rgba(0,0,0,0.55)",
    },
    maskLayer: {
      ...StyleSheet.absoluteFill,
    },
    mask: {
      position: "absolute",
      backgroundColor: "rgba(0,0,0,0.7)",
    },
    region: {
      position: "absolute",
      borderColor: "rgba(255,255,255,0.9)",
      borderWidth: StyleSheet.hairlineWidth,
      borderRadius: 10,
      backgroundColor: "transparent",
    },
    cornerTL: { ...corner, top: -2, left: -2, borderTopWidth: 3, borderLeftWidth: 3, borderTopLeftRadius: 6 },
    cornerTR: { ...corner, top: -2, right: -2, borderTopWidth: 3, borderRightWidth: 3, borderTopRightRadius: 6 },
    cornerBL: { ...corner, bottom: -2, left: -2, borderBottomWidth: 3, borderLeftWidth: 3, borderBottomLeftRadius: 6 },
    cornerBR: { ...corner, bottom: -2, right: -2, borderBottomWidth: 3, borderRightWidth: 3, borderBottomRightRadius: 6 },
    hintWrap: {
      position: "absolute",
      alignSelf: "center",
      backgroundColor: "rgba(0,0,0,0.55)",
      borderRadius: 14,
      paddingHorizontal: 14,
      paddingVertical: 7,
      zIndex: 10,
    },
    hint: {
      color: "#fff",
      fontSize: 14,
      fontWeight: "600",
      textAlign: "center",
    },
    error: {
      position: "absolute",
      bottom: 140,
      alignSelf: "center",
      color: theme.danger,
      backgroundColor: "rgba(0,0,0,0.65)",
      paddingHorizontal: 12,
      paddingVertical: 8,
      borderRadius: 8,
      overflow: "hidden",
      zIndex: 10,
    },
    controls: {
      position: "absolute",
      left: 0,
      right: 0,
      bottom: 0,
      alignItems: "center",
      zIndex: 10,
    },
    shutter: {
      width: 76,
      height: 76,
      borderRadius: 38,
      borderWidth: 4,
      borderColor: "#fff",
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: "rgba(255,255,255,0.18)",
    },
    shutterInner: {
      width: 60,
      height: 60,
      borderRadius: 30,
      backgroundColor: "#fff",
    },
    center: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: 32,
      gap: 16,
    },
    permissionText: {
      color: "#fff",
      fontSize: 16,
      textAlign: "center",
      lineHeight: 22,
    },
    permissionBtn: {
      backgroundColor: theme.primary,
      paddingHorizontal: 20,
      paddingVertical: 12,
      borderRadius: 12,
    },
    permissionBtnText: {
      color: theme.onPrimary,
      fontSize: 16,
      fontWeight: "700",
    },
  });
}
