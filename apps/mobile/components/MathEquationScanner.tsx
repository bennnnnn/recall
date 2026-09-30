import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Linking,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { useCameraPermissions } from "expo-camera";
import * as ImageManipulator from "expo-image-manipulator";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { MathScannerChrome } from "@/components/mathScanner/MathScannerChrome";
import {
  MathScannerCropOverlay,
  type LiveScanFrameStatus,
} from "@/components/mathScanner/MathScannerCropOverlay";
import {
  LiveMathScannerCamera,
  type LiveScannerCameraHandle,
  type LiveScannerDetection,
} from "@/components/mathScanner/LiveMathScannerCamera";
import {
  ScanReadingReview,
  type ScanReadingState,
} from "@/components/mathScanner/ScanReadingReview";
import { ScannerSubjectGuide } from "@/components/mathScanner/ScannerSubjectGuide";
import { useMathScannerCrop } from "@/hooks/useMathScannerCrop";
import type { PendingAttachment } from "@/features/attachments/model/attachments";
import type { MathScanReading } from "@/lib/api";
import {
  HeicUnsupportedError,
  NativePickerBusyError,
  NativePickerTimeoutError,
  pickImageDocument,
} from "@/features/attachments/model/attachments";
import { cameraPermissionNeedsSettings } from "@/lib/cameraPermission";
import { impactMedium, selection } from "@/lib/haptics";
import { useReduceMotion } from "@/lib/motion";
import {
  containedPhotoRegion,
  defaultScanRegion,
  regionToContainedImageCrop,
  regionToImageCrop,
  scanChromeInset,
  type ScanRegion,
} from "@/lib/math/scannerRegion";
import {
  playScannerSwitchCue,
  stopScannerSwitchCue,
} from "@/lib/scanner/switchCue";
import { SCANNER_SUBJECTS, type ScannerSubject } from "@/lib/scanner/subjects";
import { scheduleIdlePromise } from "@/lib/scheduleIdle";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { FullScreenModal } from "@/ui/overlay/FullScreenModal";

type Props = {
  visible: boolean;
  onClose: () => void;
  /** Send the photo; ``confirmedReading`` when the student checked the read. */
  onCaptured: (
    pending: PendingAttachment,
    subject: ScannerSubject,
    confirmedReading?: string,
  ) => void;
  /** Math only: read the crop back before solving. Null means it failed. */
  onReadScan?: (scan: PendingAttachment, signal: AbortSignal) => Promise<MathScanReading | null>;
  /** Math only: solve the confirmed reading as typed text. */
  onSolveReading?: (reading: string) => void;
};

type Review = { shot: PendingAttachment; state: ScanReadingState };

type ScanShot = PendingAttachment & { width: number; height: number };

const ANDROID_DISMISS_MS = 400;

/**
 * Keep the crop frame live over the camera so the student aims before capture.
 * Camera shots are cropped immediately from that live region; imported photos
 * still get an adjustable still-image crop. A math crop is then read back
 * ("I read this as") so a misread digit can be fixed before solving.
 */
export function MathEquationScanner({
  visible,
  onClose,
  onCaptured,
  onReadScan,
  onSolveReading,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { width: windowWidth, height: windowHeight } = useWindowDimensions();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const reduceMotion = useReduceMotion();
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<LiveScannerCameraHandle>(null);
  const [hosted, setHosted] = useState(visible);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ScanShot | null>(null);
  const [torchOn, setTorchOn] = useState(false);
  const [subject, setSubject] = useState<ScannerSubject>("math");
  const [review, setReview] = useState<Review | null>(null);
  const readAbortRef = useRef<AbortController | null>(null);
  const stopReading = useCallback(() => {
    readAbortRef.current?.abort();
    readAbortRef.current = null;
  }, []);
  const [zoom, setZoom] = useState(0);
  const [cameraReady, setCameraReady] = useState(false);
  const [liveRegion, setLiveRegion] = useState<ScanRegion | null>(null);
  const [liveStatus, setLiveStatus] = useState<LiveScanFrameStatus>("idle");
  const liveReadyRef = useRef(false);
  const capturePendingRef = useRef(false);
  const handleCameraReady = useCallback(() => setCameraReady(true), []);
  const inset = useMemo(
    () => scanChromeInset(windowWidth, windowHeight, insets),
    [windowWidth, windowHeight, insets],
  );
  const handleRegionChange = useCallback((region: ScanRegion) => {
    setLiveRegion(region);
    setLiveStatus("idle");
    liveReadyRef.current = false;
  }, []);
  const crop = useMathScannerCrop({
    windowWidth,
    windowHeight,
    inset,
    preview: Boolean(preview),
    reduceMotion,
    onZoom: setZoom,
    onRegionChange: handleRegionChange,
  });
  const scanRegion = liveRegion ?? defaultScanRegion(inset);

  const handleLiveDetection = useCallback((detection: LiveScannerDetection) => {
    const next: LiveScanFrameStatus = detection.stable
      ? "ready"
      : detection.hasText
        ? "detecting"
        : "idle";
    setLiveStatus(next);
    if (detection.stable && !liveReadyRef.current) selection();
    liveReadyRef.current = detection.stable;
  }, []);

  const previewFrame = useMemo(
    () => preview
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
      setReview(null);
      setError(null);
      setTorchOn(false);
      setCameraReady(false);
      setLiveStatus("idle");
      liveReadyRef.current = false;
      crop.resetRegion();
      crop.resetZoom();
      return;
    }
    stopScannerSwitchCue();
    if (Platform.OS === "ios") return;
    const timer = setTimeout(() => setHosted(false), ANDROID_DISMISS_MS);
    return () => clearTimeout(timer);
    // Reset live session when opening; crop helpers are stable enough per open.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- open-only reset
  }, [visible]);

  useEffect(() => stopScannerSwitchCue, []);
  useEffect(() => {
    if (!visible) stopReading();
  }, [stopReading, visible]);
  useEffect(() => stopReading, [stopReading]);

  const showShot = useCallback(
    async (pending: PendingAttachment, width = 0, height = 0) => {
      try {
        const size =
          width > 0 && height > 0 ? { width, height } : await measureImageSize(pending.localUri);
        setPreview({ ...pending, ...size });
      } catch {
        setError(t("chat.math_scan_failed"));
      }
    },
    [t],
  );

  const handleCroppedShot = useCallback(
    (cropped: PendingAttachment) => {
      if (subject === "math" && onReadScan && onSolveReading) {
        stopReading();
        const controller = new AbortController();
        readAbortRef.current = controller;
        setLiveStatus("idle");
        liveReadyRef.current = false;
        setReview({ shot: cropped, state: { status: "reading" } });
        void onReadScan(cropped, controller.signal)
          .catch(() => null)
          .then((result) => {
            if (controller.signal.aborted) return;
            readAbortRef.current = null;
            setReview((current) => {
              if (!current || current.shot !== cropped) return current;
              const reading = result?.reading.trim() ?? "";
              return {
                shot: cropped,
                state: reading
                  ? { status: "ready", reading, uncertain: Boolean(result?.uncertain) }
                  : { status: "failed" },
              };
            });
          });
        return;
      }
      onCaptured(cropped, subject);
    },
    [onCaptured, onReadScan, onSolveReading, stopReading, subject],
  );

  const capture = useCallback(async () => {
    if (!cameraRef.current || busy || preview || !cameraReady || capturePendingRef.current) return;
    capturePendingRef.current = true;
    try {
      if (!cameraRef.current || busy || preview || !cameraReady) return;
      impactMedium();
      setBusy(true);
      setError(null);
      const photo = await cameraRef.current.takePictureAsync();
      if (!photo?.uri) {
        setError(t("chat.math_scan_failed"));
        return;
      }
      const pending: PendingAttachment = {
        localUri: photo.uri,
        contentType: "image/jpeg",
        fileName: `${subject}-scan-${Date.now()}.jpg`,
        kind: "image",
      };
      const measured = await measureImageSize(photo.uri).catch(() => ({
        width: photo.width ?? 0,
        height: photo.height ?? 0,
      }));
      const width = measured.width;
      const height = measured.height;
      if (width <= 0 || height <= 0) {
        await showShot(pending);
        return;
      }

      const shot: ScanShot = { ...pending, width, height };
      try {
        const cropped = await cropShotToRegion(
          shot,
          crop.readRegion(),
          windowWidth,
          windowHeight,
          null,
        );
        handleCroppedShot(cropped);
      } catch {
        // Keep a recoverable path if a device reports unexpected camera geometry.
        await showShot(pending, width, height);
      }
    } catch {
      setError(t("chat.math_scan_failed"));
    } finally {
      setBusy(false);
      capturePendingRef.current = false;
    }
  }, [
    busy,
    cameraReady,
    crop,
    handleCroppedShot,
    preview,
    showShot,
    subject,
    t,
    windowHeight,
    windowWidth,
  ]);

  const confirmPreview = useCallback(async () => {
    if (!preview || busy) return;
    setBusy(true);
    setError(null);
    try {
      const cropped = await cropShotToRegion(
        preview,
        crop.readRegion(),
        windowWidth,
        windowHeight,
        previewFrame,
      );
      handleCroppedShot(cropped);
    } catch {
      setError(t("chat.math_scan_failed"));
    } finally {
      setBusy(false);
    }
  }, [
    busy,
    crop,
    handleCroppedShot,
    preview,
    previewFrame,
    t,
    windowWidth,
    windowHeight,
  ]);

  const retakeFromReview = useCallback(() => {
    stopReading();
    setReview(null);
    setLiveStatus("idle");
    liveReadyRef.current = false;
    crop.resetRegion();
    setPreview(null);
    setError(null);
  }, [crop, stopReading]);

  const changeSubject = useCallback((next: ScannerSubject) => {
    if (next === subject) return;
    const currentIndex = SCANNER_SUBJECTS.indexOf(next);
    const previousIndex = SCANNER_SUBJECTS.indexOf(subject);
    selection();
    void playScannerSwitchCue(currentIndex > previousIndex ? 1 : -1);
    setLiveStatus("idle");
    liveReadyRef.current = false;
    setSubject(next);
  }, [subject]);

  const openLibrary = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await scheduleIdlePromise();
      const picked = await pickImageDocument();
      if (picked) {
        setLiveStatus("idle");
        liveReadyRef.current = false;
        await showShot(picked);
      }
    } catch (caught) {
      if (caught instanceof HeicUnsupportedError) {
        setError(t("chat.heic_unsupported_body"));
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
    <FullScreenModal
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
              <LiveMathScannerCamera
                ref={cameraRef}
                active={!preview && !review && visible}
                torchOn={torchOn && !preview && !review && visible}
                zoom={zoom}
                scanRegion={scanRegion}
                onReady={handleCameraReady}
                onError={() => setError(t("chat.math_scan_camera_unavailable"))}
                onDetectionChange={handleLiveDetection}
              />
            </View> : null}
            {granted && !preview && !review ? <ScannerSubjectGuide subject={subject} /> : null}
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
                  resizeMode="contain"
                />
              </View>
            ) : null}
            {preview || (granted && !review) ? (
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
                scanning={Boolean(preview) && !busy}
                liveStatus={preview ? "idle" : liveStatus}
                onGrow={crop.growRegion}
                onShrink={crop.shrinkRegion}
              />
            ) : null}
          </View>
        )}
        <MathScannerChrome
          insets={insets}
          granted={granted}
          preview={Boolean(preview)}
          busy={busy}
          torchOn={torchOn}
          subject={subject}
          error={error}
          onClose={onClose}
          onSubjectChange={changeSubject}
          onToggleTorch={() => {
            selection();
            setTorchOn((on) => !on);
          }}
          onOpenLibrary={() => void openLibrary()}
          onCapture={() => void capture()}
          onRetake={() => {
            setLiveStatus("idle");
            liveReadyRef.current = false;
            crop.resetRegion();
            setPreview(null);
            setError(null);
          }}
          onSolve={() => void confirmPreview()}
        />
        {review ? (
          <ScanReadingReview
            photoUri={review.shot.localUri}
            state={review.state}
            insets={insets}
            onSolve={(reading) => {
              stopReading();
              onSolveReading?.(reading);
            }}
            onSendPhoto={(reading) => {
              stopReading();
              onCaptured(review.shot, "math", reading || undefined);
            }}
            onRetake={retakeFromReview}
          />
        ) : null}
      </GestureHandlerRootView>
    </FullScreenModal>
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
      ...Weight.bold,
    },
    permissionSecondary: {
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
    },
    permissionSecondaryText: {
      ...Type.label,
      color: theme.onMedia,
      ...Weight.bold,
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
