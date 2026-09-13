import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Linking,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as ImageManipulator from "expo-image-manipulator";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { MathScannerChrome } from "@/components/mathScanner/MathScannerChrome";
import { MathScannerCropOverlay } from "@/components/mathScanner/MathScannerCropOverlay";
import { useMathScannerCrop } from "@/hooks/useMathScannerCrop";
import type { PendingAttachment } from "@/lib/attachments";
import {
  HeicUnsupportedError,
  NativePickerBusyError,
  NativePickerTimeoutError,
  PhotoLibraryPermissionError,
  pickFromPhotoLibrary,
} from "@/lib/attachments";
import { cameraPermissionNeedsSettings } from "@/lib/cameraPermission";
import { impactMedium, selection } from "@/lib/haptics";
import { useReduceMotion } from "@/lib/motion";
import {
  containedPhotoRegion,
  regionToContainedImageCrop,
  regionToImageCrop,
  scanChromeInset,
  type ScanRegion,
} from "@/lib/math/mathScannerRegion";
import { useLastPhotoThumb } from "@/lib/lastPhotoThumbnail";
import { scheduleIdlePromise } from "@/lib/scheduleIdle";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  visible: boolean;
  onClose: () => void;
  onCaptured: (pending: PendingAttachment) => void;
};

type ScanShot = PendingAttachment & { width: number; height: number; fromLibrary: boolean };

const ANDROID_DISMISS_MS = 400;

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
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const [hosted, setHosted] = useState(visible);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ScanShot | null>(null);
  const [torchOn, setTorchOn] = useState(false);
  const [zoom, setZoom] = useState(0);
  const [cameraReady, setCameraReady] = useState(false);
  const lastPhotoUri = useLastPhotoThumb(visible);
  const handleCameraReady = useCallback(() => setCameraReady(true), []);
  const inset = useMemo(
    () => scanChromeInset(windowWidth, windowHeight, insets),
    [windowWidth, windowHeight, insets],
  );
  const crop = useMathScannerCrop({
    windowWidth,
    windowHeight,
    inset,
    preview: Boolean(preview),
    reduceMotion,
    onZoom: setZoom,
  });

  const previewFrame = useMemo(
    () => preview?.fromLibrary
      ? containedPhotoRegion(preview.width, preview.height, windowWidth, windowHeight, inset)
      : null,
    [inset, preview, windowHeight, windowWidth],
  );
  const resetCropRegion = crop.resetRegion;
  useEffect(() => {
    if (previewFrame) resetCropRegion(previewFrame);
  }, [previewFrame, resetCropRegion]);

  useEffect(() => {
    if (visible) {
      setHosted(true);
      setPreview(null);
      setError(null);
      setTorchOn(false);
      crop.resetRegion();
      crop.resetZoom();
      return;
    }
    if (Platform.OS === "ios") return;
    const timer = setTimeout(() => setHosted(false), ANDROID_DISMISS_MS);
    return () => clearTimeout(timer);
    // Reset live session when opening; crop helpers are stable enough per open.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- open-only reset
  }, [visible]);

  const showShot = useCallback(
    async (pending: PendingAttachment, width = 0, height = 0, fromLibrary = false) => {
      try {
        const size =
          width > 0 && height > 0 ? { width, height } : await measureImageSize(pending.localUri);
        setPreview({ ...pending, ...size, fromLibrary });
      } catch {
        setError(t("chat.math_scan_failed"));
      }
    },
    [t],
  );

  const capture = useCallback(async () => {
    if (!cameraRef.current || busy || preview || !cameraReady) return;
    impactMedium();
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
  }, [busy, cameraReady, preview, showShot, t]);

  const confirmPreview = useCallback(async () => {
    if (!preview || busy) return;
    setBusy(true);
    setError(null);
    try {
      const cropped = await cropShotToRegion(preview, crop.readRegion(), windowWidth, windowHeight, previewFrame);
      onCaptured(cropped);
    } catch {
      setError(t("chat.math_scan_failed"));
    } finally {
      setBusy(false);
    }
  }, [busy, crop, onCaptured, preview, previewFrame, t, windowWidth, windowHeight]);

  const openLibrary = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await scheduleIdlePromise();
      const picked = await pickFromPhotoLibrary();
      if (picked) await showShot(picked, 0, 0, true);
    } catch (caught) {
      if (caught instanceof HeicUnsupportedError) {
        setError(t("chat.heic_unsupported_body"));
      } else if (caught instanceof PhotoLibraryPermissionError) {
        if (caught.needsSettings) void Linking.openSettings();
        setError(t("chat.photos_permission"));
      } else if (caught instanceof NativePickerBusyError || caught instanceof NativePickerTimeoutError) {
        setError(t("chat.picker_busy"));
      } else {
        setError(t("chat.math_scan_failed"));
      }
    } finally {
      setBusy(false);
    }
  }, [busy, showShot, t]);

  const granted = Boolean(permission?.granted);

  if (!hosted && !visible) return null;

  return (
    <Modal
      visible={visible}
      animationType="fade"
      presentationStyle="fullScreen"
      statusBarTranslucent
      onRequestClose={onClose}
      onDismiss={() => setHosted(false)}
      testID="math-scanner-modal"
    >
      <GestureHandlerRootView style={s.root}>
        {!permission && !preview ? (
          <View style={s.center}>
            <ActivityIndicator color={theme.onMedia} />
          </View>
        ) : !granted && !preview ? (
          <View style={s.center}>
            <Text style={s.permissionText}>{t("chat.math_scan_permission")}</Text>
            <Pressable
              style={s.permissionBtn}
              testID="math-scanner-permission"
              accessibilityRole="button"
              accessibilityLabel={
                cameraPermissionNeedsSettings(permission)
                  ? t("chat.location_open_settings")
                  : t("chat.math_scan_allow_camera")
              }
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
            {granted ? <View style={StyleSheet.absoluteFill} testID="math-scanner-camera" pointerEvents="none">
              <CameraView
                ref={cameraRef}
                style={StyleSheet.absoluteFill}
                facing="back"
                mode="picture"
                zoom={zoom}
                enableTorch={torchOn && !preview && visible}
                flash="off"
                autofocus="off"
                animateShutter={false}
                active={!preview && visible}
                onCameraReady={handleCameraReady}
                onMountError={() => setError(t("chat.math_scan_camera_unavailable"))}
              />
            </View> : null}
            {preview ? (
              <View style={[StyleSheet.absoluteFill, { backgroundColor: theme.mediaScrim }]}>
                <Image
                  source={{ uri: preview.localUri }}
                  testID="math-scanner-preview"
                  style={previewFrame ? {
                    position: "absolute",
                    left: previewFrame.x * windowWidth,
                    top: previewFrame.y * windowHeight,
                    width: previewFrame.width * windowWidth,
                    height: previewFrame.height * windowHeight,
                  } : StyleSheet.absoluteFill}
                  resizeMode={previewFrame ? "contain" : "cover"}
                />
              </View>
            ) : null}
            <MathScannerCropOverlay
              regionGesture={crop.regionGesture}
              cornerTL={crop.cornerTL}
              cornerTR={crop.cornerTR}
              cornerBL={crop.cornerBL}
              cornerBR={crop.cornerBR}
              regionStyle={crop.regionStyle}
              maskTopStyle={crop.maskTopStyle}
              maskBottomStyle={crop.maskBottomStyle}
              maskLeftStyle={crop.maskLeftStyle}
              maskRightStyle={crop.maskRightStyle}
              handleTLStyle={crop.handleTLStyle}
              handleTRStyle={crop.handleTRStyle}
              handleBLStyle={crop.handleBLStyle}
              handleBRStyle={crop.handleBRStyle}
              onGrow={crop.growRegion}
              onShrink={crop.shrinkRegion}
            />
          </View>
        )}
        <MathScannerChrome
          insets={insets}
          granted={granted}
          preview={Boolean(preview)}
          busy={busy}
          torchOn={torchOn}
          error={error}
          lastPhotoUri={lastPhotoUri}
          onClose={onClose}
          onResetFrame={() => crop.resetRegion(previewFrame ?? undefined)}
          onToggleTorch={() => {
            selection();
            setTorchOn((on) => !on);
          }}
          onOpenLibrary={() => void openLibrary()}
          onCapture={() => void capture()}
          onRetake={() => {
            if (preview?.fromLibrary) crop.resetRegion();
            setPreview(null);
            setError(null);
          }}
          onSolve={() => void confirmPreview()}
        />
      </GestureHandlerRootView>
    </Modal>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    root: {
      flex: 1,
      backgroundColor: theme.mediaScrim,
    },
    center: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: Space.xl,
      gap: Space.md,
    },
    permissionText: {
      ...Type.body,
      color: theme.onMedia,
      textAlign: "center",
    },
    permissionBtn: {
      backgroundColor: theme.primary,
      paddingHorizontal: Space.gutter,
      paddingVertical: Space.sm,
      borderRadius: Radius.md,
    },
    permissionBtnText: {
      ...Type.label,
      color: theme.onPrimary,
      fontWeight: "700",
    },
    permissionSecondary: {
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
    },
    permissionSecondaryText: {
      ...Type.label,
      color: theme.onMedia,
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
  imageRegion: ScanRegion | null,
): Promise<PendingAttachment> {
  const crop = imageRegion
    ? regionToContainedImageCrop(region, imageRegion, shot.width, shot.height)
    : regionToImageCrop(region, shot.width, shot.height, windowWidth, windowHeight);
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
