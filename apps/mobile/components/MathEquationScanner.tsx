import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Animated,
  Image,
  Linking,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as ImageManipulator from "expo-image-manipulator";
import {
  Gesture,
  GestureDetector,
  GestureHandlerRootView,
  Pressable as GHPressable,
} from "react-native-gesture-handler";
import { runOnJS } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import type { PendingAttachment } from "@/lib/attachments";
import { HeicUnsupportedError, pickFromPhotoLibrary } from "@/lib/attachments";
import { cameraPermissionNeedsSettings } from "@/lib/cameraPermission";
import { impactMedium, selection, tap } from "@/lib/haptics";
import { useReduceMotion } from "@/lib/reduceMotion";
import {
  clampFocusInRegion,
  defaultScanRegion,
  FOCUS_SQUARE_SIZE,
  regionToImageCrop,
  resizeScanRegionFromCorner,
  scaleScanRegion,
  translateScanRegion,
  zoomFromPinch,
  type FocusInRegion,
  type ScanCorner,
  type ScanRegion,
} from "@/lib/math/mathScannerRegion";
import { Theme, useTheme, withAlpha } from "@/lib/theme";

type Props = {
  visible: boolean;
  onClose: () => void;
  onCaptured: (pending: PendingAttachment) => void;
};

type ScanShot = PendingAttachment & { width: number; height: number };

const HANDLE = 44;
const FOCUS_MS = 900;
const TORCH_ON_COLOR = "#FFD60A";
const SHUTTER_FLASH_MS = 160;

/**
 * Live camera to frame a problem, then a still-photo crop. Solve crops that
 * rectangle and sends the image to chat — no separate OCR round-trip.
 */
export function MathEquationScanner({ visible, onClose, onCaptured }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { width: windowWidth, height: windowHeight } = useWindowDimensions();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const reduceMotion = useReduceMotion();
  const flashOpacity = useRef(new Animated.Value(0)).current;
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ScanShot | null>(null);
  const [region, setRegion] = useState<ScanRegion>(defaultScanRegion());
  const [torchOn, setTorchOn] = useState(false);
  const [zoom, setZoom] = useState(0);
  const [autofocus, setAutofocus] = useState<"on" | "off">("off");
  const [focusPoint, setFocusPoint] = useState<FocusInRegion | null>(null);
  const regionRef = useRef(region);
  regionRef.current = region;
  const zoomRef = useRef(zoom);
  zoomRef.current = zoom;
  const previewRef = useRef(preview);
  previewRef.current = preview;
  const regionWidthRef = useRef(0);
  const regionHeightRef = useRef(0);
  const pinchStartZoomRef = useRef(0);
  const pinchStartRegionRef = useRef(region);
  const panBaseRef = useRef(region);
  const cornerBaseRef = useRef(region);
  const focusTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const resetLive = useCallback(() => {
    setPreview(null);
    setError(null);
    setTorchOn(false);
    setZoom(0);
    setAutofocus("off");
    setFocusPoint(null);
  }, []);

  useEffect(() => {
    if (!visible) resetLive();
  }, [visible, resetLive]);

  useEffect(() => {
    return () => {
      if (focusTimerRef.current) clearTimeout(focusTimerRef.current);
    };
  }, []);

  const beginPan = useCallback(() => {
    panBaseRef.current = regionRef.current;
  }, []);
  const applyPanDelta = useCallback((dxRatio: number, dyRatio: number) => {
    setRegion(translateScanRegion(panBaseRef.current, dxRatio, dyRatio));
  }, []);
  const beginCorner = useCallback(() => {
    cornerBaseRef.current = regionRef.current;
  }, []);
  const applyCorner = useCallback((corner: ScanCorner, dxRatio: number, dyRatio: number) => {
    setRegion(resizeScanRegionFromCorner(cornerBaseRef.current, corner, dxRatio, dyRatio));
  }, []);

  const beginPinch = useCallback(() => {
    pinchStartZoomRef.current = zoomRef.current;
    pinchStartRegionRef.current = regionRef.current;
  }, []);
  const applyPinch = useCallback((scale: number) => {
    if (previewRef.current) {
      setRegion(scaleScanRegion(pinchStartRegionRef.current, scale));
      return;
    }
    setZoom(zoomFromPinch(pinchStartZoomRef.current, scale));
  }, []);

  const onFocusTap = useCallback((localX: number, localY: number) => {
    if (previewRef.current) return;
    const next = clampFocusInRegion(localX, localY, regionWidthRef.current, regionHeightRef.current);
    if (!next) return;
    tap();
    setFocusPoint(next);
    setAutofocus("on");
    if (focusTimerRef.current) clearTimeout(focusTimerRef.current);
    focusTimerRef.current = setTimeout(() => {
      setAutofocus("off");
      setFocusPoint(null);
    }, FOCUS_MS);
  }, []);

  const playCaptureFlash = useCallback(() => {
    if (reduceMotion) return;
    flashOpacity.setValue(0.88);
    Animated.timing(flashOpacity, {
      toValue: 0,
      duration: SHUTTER_FLASH_MS,
      useNativeDriver: true,
    }).start();
  }, [flashOpacity, reduceMotion]);

  const pinchGesture = useMemo(
    () =>
      Gesture.Pinch()
        .onBegin(() => {
          runOnJS(beginPinch)();
        })
        .onUpdate((e) => {
          runOnJS(applyPinch)(e.scale);
        }),
    [applyPinch, beginPinch],
  );
  const tapGesture = useMemo(
    () =>
      Gesture.Tap()
        .maxDistance(10)
        .onEnd((e, success) => {
          if (success) runOnJS(onFocusTap)(e.x, e.y);
        }),
    [onFocusTap],
  );
  const panGesture = useMemo(
    () =>
      Gesture.Pan()
        .maxPointers(1)
        .activeOffsetX([-12, 12])
        .activeOffsetY([-12, 12])
        .onBegin(() => {
          runOnJS(beginPan)();
        })
        .onUpdate((e) => {
          runOnJS(applyPanDelta)(e.translationX / windowWidth, e.translationY / windowHeight);
        }),
    [applyPanDelta, beginPan, windowWidth, windowHeight],
  );
  const regionGesture = useMemo(
    () => Gesture.Simultaneous(pinchGesture, Gesture.Exclusive(panGesture, tapGesture)),
    [pinchGesture, panGesture, tapGesture],
  );

  const makeCornerGesture = useCallback(
    (corner: ScanCorner) =>
      Gesture.Pan()
        .maxPointers(1)
        .onBegin(() => {
          runOnJS(beginCorner)();
        })
        .onUpdate((e) => {
          runOnJS(applyCorner)(corner, e.translationX / windowWidth, e.translationY / windowHeight);
        }),
    [applyCorner, beginCorner, windowWidth, windowHeight],
  );
  const cornerTL = useMemo(() => makeCornerGesture("tl"), [makeCornerGesture]);
  const cornerTR = useMemo(() => makeCornerGesture("tr"), [makeCornerGesture]);
  const cornerBL = useMemo(() => makeCornerGesture("bl"), [makeCornerGesture]);
  const cornerBR = useMemo(() => makeCornerGesture("br"), [makeCornerGesture]);

  const regionLeft = Math.round(region.x * windowWidth);
  const regionTop = Math.round(region.y * windowHeight);
  const regionWidth = Math.round(region.width * windowWidth);
  const regionHeight = Math.round(region.height * windowHeight);
  regionWidthRef.current = regionWidth;
  regionHeightRef.current = regionHeight;
  const regionRight = regionLeft + regionWidth;
  const regionBottom = regionTop + regionHeight;

  const showShot = useCallback(async (pending: PendingAttachment, width = 0, height = 0) => {
    try {
      const size =
        width > 0 && height > 0 ? { width, height } : await measureImageSize(pending.localUri);
      setPreview({ ...pending, ...size });
    } catch {
      setError(t("chat.math_scan_failed"));
    }
  }, [t]);

  const capture = useCallback(async () => {
    if (!cameraRef.current || busy || preview) return;
    impactMedium();
    playCaptureFlash();
    setBusy(true);
    setError(null);
    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.9,
        shutterSound: true,
        exif: true,
      });
      if (!photo?.uri) {
        setError(t("chat.math_scan_failed"));
        return;
      }
      await showShot(
        {
          localUri: photo.uri,
          contentType: "image/jpeg",
          fileName: `math-scan-${Date.now()}.jpg`,
          kind: "image",
        },
        photo.width ?? 0,
        photo.height ?? 0,
      );
    } catch {
      setError(t("chat.math_scan_failed"));
    } finally {
      setBusy(false);
    }
  }, [busy, playCaptureFlash, preview, showShot, t]);

  const closeScanner = useCallback(() => {
    setTorchOn(false);
    onClose();
  }, [onClose]);

  const toggleTorch = useCallback(() => {
    selection();
    setTorchOn((on) => !on);
  }, []);

  const confirmPreview = useCallback(async () => {
    if (!preview || busy) return;
    setBusy(true);
    setError(null);
    try {
      const cropped = await cropShotToRegion(preview, regionRef.current, windowWidth, windowHeight);
      onCaptured(cropped);
      resetLive();
    } catch {
      setError(t("chat.math_scan_failed"));
    } finally {
      setBusy(false);
    }
  }, [busy, onCaptured, preview, resetLive, t, windowWidth, windowHeight]);

  const retakePreview = useCallback(() => {
    setPreview(null);
    setError(null);
  }, []);

  const openLibrary = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const picked = await pickFromPhotoLibrary();
      if (picked) await showShot(picked);
    } catch (error) {
      if (error instanceof HeicUnsupportedError) {
        setError(t("chat.heic_unsupported_body"));
      } else {
        setError(error instanceof Error ? error.message : t("chat.math_scan_failed"));
      }
    } finally {
      setBusy(false);
    }
  }, [busy, showShot, t]);

  const granted = Boolean(permission?.granted);
  const cropChrome = (
    <>
      <View style={s.maskLayer} pointerEvents="box-none">
        <View style={[s.mask, { top: 0, left: 0, right: 0, height: regionTop }]} />
        <View style={[s.mask, { top: regionBottom, left: 0, right: 0, bottom: 0 }]} />
        <View
          style={[s.mask, { top: regionTop, left: 0, width: regionLeft, height: regionHeight }]}
        />
        <View
          style={[s.mask, { top: regionTop, left: regionRight, right: 0, height: regionHeight }]}
        />
      </View>
      <GestureDetector gesture={regionGesture}>
        <View
          style={[
            s.region,
            { left: regionLeft, top: regionTop, width: regionWidth, height: regionHeight },
          ]}
          collapsable={false}
          accessibilityLabel={t("chat.math_scan_frame_a11y")}
        >
          <View style={s.cornerTL} />
          <View style={s.cornerTR} />
          <View style={s.cornerBL} />
          <View style={s.cornerBR} />
          {focusPoint && !preview ? (
            <View
              pointerEvents="none"
              style={[
                s.focusSquare,
                {
                  width: focusPoint.size,
                  height: focusPoint.size,
                  left: focusPoint.x - focusPoint.size / 2,
                  top: focusPoint.y - focusPoint.size / 2,
                },
              ]}
            />
          ) : null}
        </View>
      </GestureDetector>
      <GestureDetector gesture={cornerTL}>
        <View style={[s.handle, { left: regionLeft - HANDLE / 2, top: regionTop - HANDLE / 2 }]} />
      </GestureDetector>
      <GestureDetector gesture={cornerTR}>
        <View style={[s.handle, { left: regionRight - HANDLE / 2, top: regionTop - HANDLE / 2 }]} />
      </GestureDetector>
      <GestureDetector gesture={cornerBL}>
        <View
          style={[s.handle, { left: regionLeft - HANDLE / 2, top: regionBottom - HANDLE / 2 }]}
        />
      </GestureDetector>
      <GestureDetector gesture={cornerBR}>
        <View
          style={[s.handle, { left: regionRight - HANDLE / 2, top: regionBottom - HANDLE / 2 }]}
        />
      </GestureDetector>
    </>
  );

  const cameraLayer = preview ? (
    <View style={StyleSheet.absoluteFill} collapsable={false}>
      <Image
        source={{ uri: preview.localUri }}
        style={StyleSheet.absoluteFill}
        resizeMode="cover"
      />
      {cropChrome}
    </View>
  ) : !permission ? (
    <View style={s.center}>
      <ActivityIndicator color={theme.onMedia} />
    </View>
  ) : !granted ? (
    <View style={s.center}>
      <Text style={s.permissionText}>{t("chat.math_scan_permission")}</Text>
      <Pressable
        style={s.permissionBtn}
        onPress={() => {
          if (cameraPermissionNeedsSettings(permission)) {
            void Linking.openSettings();
            return;
          }
          void requestPermission();
        }}
      >
        <Text style={s.permissionBtnText}>
          {cameraPermissionNeedsSettings(permission)
            ? t("chat.location_open_settings")
            : t("chat.math_scan_allow_camera")}
        </Text>
      </Pressable>
      <Pressable
        style={s.permissionSecondary}
        onPress={() => void openLibrary()}
        accessibilityRole="button"
        accessibilityLabel={t("chat.math_scan_photos_a11y")}
      >
        <Text style={s.permissionSecondaryText}>{t("chat.math_scan_choose_photo")}</Text>
      </Pressable>
    </View>
  ) : (
    <View style={StyleSheet.absoluteFill} collapsable={false}>
      <View style={StyleSheet.absoluteFill} pointerEvents="none">
        <CameraView
          ref={cameraRef}
          style={StyleSheet.absoluteFill}
          facing="back"
          mode="picture"
          zoom={zoom}
          enableTorch={torchOn}
          flash="off"
          autofocus={autofocus}
          animateShutter
        />
      </View>
      {cropChrome}
    </View>
  );

  const overlay = (
    <>
      <Pressable
        style={[s.close, { top: insets.top + 8 }]}
        onPressIn={closeScanner}
        hitSlop={20}
        accessibilityRole="button"
        accessibilityLabel={t("common.close")}
      >
        <Icon name="close" size={28} color={theme.onMedia} />
      </Pressable>
      {error ? <Text style={s.error}>{error}</Text> : null}
      {preview ? (
        <View style={[s.previewActions, { paddingBottom: Math.max(insets.bottom, 16) + 12 }]}>
          <GHPressable
            style={s.previewSecondary}
            onPress={retakePreview}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel={t("chat.math_scan_retake")}
          >
            <Text style={s.previewSecondaryText}>{t("chat.math_scan_retake")}</Text>
          </GHPressable>
          <GHPressable
            style={s.previewPrimary}
            onPress={() => void confirmPreview()}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel={t("chat.math_scan_solve")}
          >
            {busy ? (
              <ActivityIndicator color={theme.onPrimary} />
            ) : (
              <Text style={s.previewPrimaryText}>{t("chat.math_scan_solve")}</Text>
            )}
          </GHPressable>
        </View>
      ) : granted ? (
        <View style={[s.controls, { paddingBottom: Math.max(insets.bottom, 16) + 12 }]}>
          <GHPressable
            style={s.photosBtn}
            onPress={() => void openLibrary()}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel={t("chat.math_scan_photos_a11y")}
          >
            <Icon name="images-outline" size={26} color={theme.onMedia} />
            <Text style={s.photosLabel}>{t("chat.math_scan_photos")}</Text>
          </GHPressable>
          <GHPressable
            style={s.shutter}
            onPressIn={() => void capture()}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel={t("chat.math_scan_capture_a11y")}
          >
            {busy ? <ActivityIndicator color={theme.text} /> : <View style={s.shutterInner} />}
          </GHPressable>
          <GHPressable
            style={[s.photosBtn, torchOn ? s.torchOn : null]}
            onPress={toggleTorch}
            accessibilityRole="button"
            accessibilityState={{ selected: torchOn }}
            accessibilityLabel={
              torchOn ? t("chat.math_scan_torch_on_a11y") : t("chat.math_scan_torch_off_a11y")
            }
          >
            <Icon
              name={torchOn ? "flashlight" : "flashlight-outline"}
              size={26}
              color={torchOn ? TORCH_ON_COLOR : theme.onMedia}
              style={s.torchIcon}
            />
          </GHPressable>
        </View>
      ) : null}
      <Animated.View
        pointerEvents="none"
        style={[s.shutterFlash, { opacity: flashOpacity }]}
      />
    </>
  );

  if (!visible) return null;

  return (
    <Modal
      visible={visible}
      animationType="fade"
      presentationStyle="fullScreen"
      onRequestClose={closeScanner}
    >
      <GestureHandlerRootView style={s.root}>
        <View style={s.cameraLayer}>{cameraLayer}</View>
        <View style={s.overlayLayer} pointerEvents="box-none" collapsable={false}>
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
      backgroundColor: theme.mediaScrim,
    },
    cameraLayer: {
      ...StyleSheet.absoluteFill,
      zIndex: 1,
    },
    overlayLayer: {
      ...StyleSheet.absoluteFill,
      zIndex: 40,
      elevation: 20,
    },
    close: {
      position: "absolute",
      left: 16,
      zIndex: 50,
      width: 44,
      height: 40,
      borderRadius: 20,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: withAlpha(theme.mediaScrim, 0.55),
    },
    maskLayer: {
      ...StyleSheet.absoluteFill,
    },
    mask: {
      position: "absolute",
      backgroundColor: withAlpha(theme.mediaScrim, 0.7),
    },
    region: {
      position: "absolute",
      borderColor: withAlpha(theme.onMedia, 0.9),
      borderWidth: StyleSheet.hairlineWidth,
      borderRadius: 10,
      backgroundColor: "transparent",
      zIndex: 4,
    },
    handle: {
      position: "absolute",
      width: HANDLE,
      height: HANDLE,
      zIndex: 8,
    },
    cornerTL: { ...corner, top: -2, left: -2, borderTopWidth: 3, borderLeftWidth: 3, borderTopLeftRadius: 6 },
    cornerTR: { ...corner, top: -2, right: -2, borderTopWidth: 3, borderRightWidth: 3, borderTopRightRadius: 6 },
    cornerBL: { ...corner, bottom: -2, left: -2, borderBottomWidth: 3, borderLeftWidth: 3, borderBottomLeftRadius: 6 },
    cornerBR: { ...corner, bottom: -2, right: -2, borderBottomWidth: 3, borderRightWidth: 3, borderBottomRightRadius: 6 },
    focusSquare: {
      position: "absolute",
      width: FOCUS_SQUARE_SIZE,
      height: FOCUS_SQUARE_SIZE,
      borderWidth: 1.5,
      borderColor: theme.onMedia,
      borderRadius: 8,
    },
    torchIcon: {
      transform: [{ rotate: "-45deg" }],
    },
    torchOn: {
      borderRadius: 20,
      backgroundColor: withAlpha(TORCH_ON_COLOR, 0.22),
    },
    shutterFlash: {
      ...StyleSheet.absoluteFill,
      backgroundColor: "#FFFFFF",
      zIndex: 80,
    },
    previewActions: {
      position: "absolute",
      left: 16,
      right: 16,
      bottom: 0,
      flexDirection: "row",
      gap: 12,
      zIndex: 10,
    },
    previewSecondary: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      paddingVertical: 14,
      borderRadius: 12,
      backgroundColor: withAlpha(theme.onMedia, 0.18),
      minHeight: 48,
    },
    previewSecondaryText: {
      color: theme.onMedia,
      fontSize: 16,
      fontWeight: "700",
    },
    previewPrimary: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      paddingVertical: 14,
      borderRadius: 12,
      backgroundColor: theme.primary,
      minHeight: 48,
    },
    previewPrimaryText: {
      color: theme.onPrimary,
      fontSize: 16,
      fontWeight: "700",
    },
    error: {
      position: "absolute",
      bottom: 140,
      alignSelf: "center",
      color: theme.danger,
      backgroundColor: withAlpha(theme.mediaScrim, 0.65),
      paddingHorizontal: 12,
      paddingVertical: 8,
      borderRadius: 8,
      overflow: "hidden",
      zIndex: 10,
    },
    controls: {
      position: "absolute",
      left: 16,
      right: 16,
      bottom: 0,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      zIndex: 10,
    },
    photosBtn: {
      width: 72,
      alignItems: "center",
      justifyContent: "center",
      gap: 4,
      minHeight: 48,
    },
    photosLabel: {
      color: theme.onMedia,
      fontSize: 12,
      fontWeight: "600",
    },
    shutter: {
      width: 76,
      height: 76,
      borderRadius: 38,
      borderWidth: 4,
      borderColor: theme.onMedia,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: withAlpha(theme.onMedia, 0.18),
    },
    shutterInner: {
      width: 60,
      height: 60,
      borderRadius: 30,
      backgroundColor: theme.onMedia,
    },
    center: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: 32,
      gap: 16,
    },
    permissionText: {
      color: theme.onMedia,
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
    permissionSecondary: {
      paddingHorizontal: 16,
      paddingVertical: 10,
    },
    permissionSecondaryText: {
      color: theme.onMedia,
      fontSize: 16,
      fontWeight: "700",
    },
  });
}

function measureImageSize(uri: string): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    Image.getSize(
      uri,
      (width, height) => {
        if (width > 0 && height > 0) resolve({ width, height });
        else reject(new Error("invalid image size"));
      },
      reject,
    );
  });
}

async function cropShotToRegion(
  shot: ScanShot,
  region: ScanRegion,
  windowWidth: number,
  windowHeight: number,
): Promise<PendingAttachment> {
  const crop = regionToImageCrop(region, shot.width, shot.height, windowWidth, windowHeight);
  const result = await ImageManipulator.manipulateAsync(
    shot.localUri,
    [{ crop }],
    { compress: 0.9, format: ImageManipulator.SaveFormat.JPEG },
  );
  return {
    localUri: result.uri,
    contentType: "image/jpeg",
    fileName: shot.fileName,
    kind: "image",
  };
}
