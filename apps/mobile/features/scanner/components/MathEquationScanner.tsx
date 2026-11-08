import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  type LayoutChangeEvent,
  Platform,
  StyleSheet,
  View,
  useWindowDimensions,
} from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { MathScannerChrome } from "@/features/scanner/components/MathScannerChrome";
import { MathScannerCropOverlay } from "@/features/scanner/components/MathScannerCropOverlay";
import { LiveMathScannerCamera } from "@/features/scanner/components/LiveMathScannerCamera";
import { ScannerCameraUnavailable } from "@/features/scanner/components/ScannerCameraUnavailable";
import { ScannerFocusArea, ScannerFocusRing } from "@/features/scanner/components/ScannerFocusRing";
import { ScannerPermission } from "@/features/scanner/components/ScannerPermission";
import { ScannerPreviewImage } from "@/features/scanner/components/ScannerPreviewImage";
import { useLiveScanStatus } from "@/features/scanner/hooks/useLiveScanStatus";
import { useMathScannerCrop } from "@/features/scanner/hooks/useMathScannerCrop";
import { useScanContentFit } from "@/features/scanner/hooks/useScanContentFit";
import { useScannerCameraPermission } from "@/features/scanner/hooks/useScannerCameraPermission";
import { useScannerCamera } from "@/features/scanner/hooks/useScannerCamera";
import { useScannerFocus } from "@/features/scanner/hooks/useScannerFocus";
import { boxIn, type ImageBox, shotCrop, shotCutMaxEdge } from "@/features/scanner/model/contentFit";
import type { PendingAttachment } from "@/features/attachments/model/attachments";
import {
  NativePickerBusyError,
  NativePickerTimeoutError,
  pickFromPhotoLibrary,
  pickImageDocument,
} from "@/features/attachments/model/attachments";
import { impactMedium, selection } from "@/lib/haptics";
import { useReduceMotion } from "@/lib/motion";
import {
  containedPhotoRegion,
  defaultScanRegion,
  regionToContainedImageCrop,
  regionToImageCrop,
  regionsClose,
  scanChromeInset,
  type ScanRegion,
} from "@/lib/math/scannerRegion";
import { cropScanImage, measureScanImage, SCAN_MAX_EDGE, ScanFiles } from "@/features/scanner/model/scanImage";
import {
  playScannerSwitchCue,
  stopScannerSwitchCue,
} from "@/features/scanner/model/switchCue";
import { SCANNER_SUBJECTS, type ScannerSubject } from "@/lib/scanner/subjects";
import { scheduleIdlePromise } from "@/lib/scheduleIdle";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { FullScreenModal } from "@/ui/overlay/FullScreenModal";

type Props = {
  visible: boolean;
  onClose: () => void;
  /**
   * Send the cropped photo with its subject; the chat turn reads and solves it. The
   * composer then owns the file.
   */
  onCaptured: (pending: PendingAttachment, subject: ScannerSubject) => void;
};

/**
 * A still on the crop screen, with the subject its tab had when it was taken or picked, and
 * for a camera shot where the live frame was in it (the crop frame opens there).
 */
type ScanShot = PendingAttachment & { width: number; height: number; subject: ScannerSubject; aim?: ImageBox | null };

const ANDROID_DISMISS_MS = 400;

/**
 * Keep the crop frame live over the camera so the student aims before capture; a tap
 * focuses there. A camera shot is cut to that live region with room around it and shown
 * as a still with its own adjustable crop, opening on the live frame, as an imported
 * photo is; once the phone has read the still's text the frame moves onto it
 * (`useScanContentFit`). Nothing is sent until Solve. Solve sends the crop to the chat
 * with the subject, and the turn reads and solves it.
 *
 * Capture is never a silent tap: while the camera starts the shutter says so, and
 * a camera that cannot run says why in the viewfinder and offers a photo instead.
 *
 * A shot checks after every await that the scanner is still in the session it
 * started in: one that lands after close is dropped and its files deleted.
 */
export function MathEquationScanner({ visible, onClose, onCaptured }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const windowSize = useWindowDimensions();
  // The camera fills this view; the overlay and the crop map against its measured size.
  const [view, setView] = useState({ width: windowSize.width, height: windowSize.height });
  const handleLayout = useCallback((event: LayoutChangeEvent) => {
    const { width, height } = event.nativeEvent.layout;
    if (!(width > 0 && height > 0)) return;
    setView((current) =>
      current.width === width && current.height === height ? current : { width, height },
    );
  }, []);
  const s = useMemo(() => makeStyles(theme), [theme]);
  const reduceMotion = useReduceMotion();
  const [permission, requestPermission] = useScannerCameraPermission(visible);
  const granted = Boolean(permission?.granted);
  const [hosted, setHosted] = useState(visible);
  const [busy, setBusy] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ScanShot | null>(null);
  const [torchOn, setTorchOn] = useState(false);
  const [subject, setSubject] = useState<ScannerSubject>("math");
  const [files] = useState(() => new ScanFiles());
  const camera = useScannerCamera({ live: granted && visible && !preview });
  const { cameraRef, resetCamera } = camera;
  const cameraStatus = camera.status;
  // Bumped on every open and close; work started in an older session is stale.
  const sessionRef = useRef(0);
  const [zoom, setZoom] = useState(0);
  const [liveRegion, setLiveRegion] = useState<ScanRegion | null>(null);
  const { liveStatus, readEpoch, resetLive, handleLiveDetection } = useLiveScanStatus();
  // One shot at a time: a capture or a preview Solve, never two.
  const shotPendingRef = useRef(false);
  const inset = useMemo(
    () => scanChromeInset(view.width, view.height, insets),
    [view.width, view.height, insets.top, insets.bottom],
  );
  const handleRegionChange = useCallback((region: ScanRegion) => {
    setLiveRegion((current) => (current && regionsClose(current, region) ? current : region));
    resetLive();
  }, [resetLive]);
  const focus = useScannerFocus(cameraRef, granted && visible && !preview && cameraStatus.kind === "ready", inset.top * view.height);
  const crop = useMathScannerCrop({
    windowWidth: view.width,
    windowHeight: view.height,
    inset,
    preview: Boolean(preview),
    reduceMotion,
    onZoom: setZoom,
    onRegionChange: handleRegionChange,
    onTap: focus.focusAt,
  });
  const scanRegion = liveRegion ?? defaultScanRegion(inset);

  const previewFrame = useMemo(
    () => preview
      ? containedPhotoRegion(preview.width, preview.height, view.width, view.height, inset)
      : null,
    [inset, preview, view.height, view.width],
  );
  useScanContentFit({ preview, previewFrame, crop });

  useEffect(() => {
    sessionRef.current += 1;
    if (visible) {
      setHosted(true);
      setPreview(null);
      setError(null);
      setTorchOn(false);
      resetCamera();
      resetLive();
      crop.resetRegion();
      crop.resetZoom();
      return;
    }
    files.discardAll();
    stopScannerSwitchCue();
    if (Platform.OS === "ios") return;
    const timer = setTimeout(() => setHosted(false), ANDROID_DISMISS_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- open-only reset: the crop helpers are stable enough per open
  }, [visible]);

  useEffect(() => () => {
    stopScannerSwitchCue();
    files.discardAll();
  }, [files]);

  /** Show a shot for a manual crop, sized in the space the crop is cut in; `aim` is the live frame in it. */
  const showShot = useCallback(
    async (pending: PendingAttachment, shotSubject: ScannerSubject, isCurrent: () => boolean, aim: ImageBox | null = null) => {
      try {
        const size = await measureScanImage(pending.localUri);
        if (isCurrent()) setPreview({ ...pending, ...size, subject: shotSubject, aim });
        else files.discard(pending.localUri);
      } catch {
        files.discard(pending.localUri);
        if (isCurrent()) setError(t("chat.math_scan_failed"));
      }
    },
    [files, t],
  );

  /** One shot's work, told whether the scanner is still the session it started in. */
  const runShot = useCallback(async (work: (isCurrent: () => boolean) => Promise<void>) => {
    if (shotPendingRef.current) return;
    shotPendingRef.current = true;
    const session = sessionRef.current;
    const isCurrent = () => session === sessionRef.current;
    try {
      await work(isCurrent);
    } catch {
      if (isCurrent()) setError(t("chat.math_scan_failed"));
    } finally {
      shotPendingRef.current = false;
      setBusy(false);
      setCapturing(false);
    }
  }, [t]);

  /** Send a fresh crop, unless the scanner closed while it was cut. It becomes the chat's file. */
  const deliverCrop = useCallback(
    (cropped: PendingAttachment, shotSubject: ScannerSubject, isCurrent: () => boolean) => {
      files.track(cropped.localUri);
      if (!isCurrent()) {
        files.discard(cropped.localUri);
        return;
      }
      files.handOff(cropped.localUri);
      files.discardAll();
      resetLive();
      onCaptured(cropped, shotSubject);
    },
    [files, onCaptured, resetLive],
  );

  const capture = useCallback(() => {
    // The shutter is disabled until the camera is ready, and says why (MathScannerChrome).
    if (busy || preview || cameraStatus.kind !== "ready" || !cameraRef.current) return;
    const shotSubject = subject;
    const region = crop.readRegion();
    const { width: viewWidth, height: viewHeight } = view;
    void runShot(async (isCurrent) => {
      const camera = cameraRef.current;
      if (!camera) return;
      impactMedium();
      setBusy(true);
      setCapturing(true);
      setError(null);
      const photo = await camera.takePictureAsync();
      if (!photo?.uri) {
        if (isCurrent()) setError(t("chat.math_scan_failed"));
        return;
      }
      files.track(photo.uri);
      if (!isCurrent()) {
        files.discard(photo.uri);
        return;
      }
      const pending: PendingAttachment = {
        localUri: photo.uri,
        contentType: "image/jpeg",
        fileName: `${shotSubject}-scan-${Date.now()}.jpg`,
        kind: "image",
      };
      // Where the live frame is in the whole photo, and in the cut with room around it (`shotCrop`).
      const framed: { inPhoto?: ImageBox; inCut?: ImageBox } = {};
      let cropped: { uri: string };
      try {
        cropped = await cropScanImage(photo.uri, (size) => {
          const frame = regionToImageCrop(region, size.width, size.height, viewWidth, viewHeight);
          const shot = shotCrop(frame, size);
          framed.inPhoto = boxIn(frame, size);
          framed.inCut = shot.aim;
          return shot.crop;
        }, shotCutMaxEdge(SCAN_MAX_EDGE));
      } catch (error) {
        // The photo could not be cut: the whole photo comes up with the frame where it was aimed.
        console.warn("[scanner] could not cut the shot; showing the whole photo", error instanceof Error ? error.message : typeof error);
        await showShot(pending, shotSubject, isCurrent, framed.inPhoto ?? null);
        return;
      }
      // The full-resolution capture is not needed once it is cropped.
      files.discard(photo.uri);
      files.track(cropped.uri);
      if (isCurrent()) resetLive();
      // The framed shot waits on the crop screen: nothing is sent before Solve.
      await showShot({ ...pending, localUri: cropped.uri }, shotSubject, isCurrent, framed.inCut ?? null);
    });
  }, [busy, cameraRef, cameraStatus.kind, crop, files, preview, resetLive, runShot, showShot, subject, t, view]);

  const confirmPreview = useCallback(() => {
    if (!preview || busy || !previewFrame) return;
    const shotSubject = preview.subject;
    const region = crop.readRegion();
    void runShot(async (isCurrent) => {
      setBusy(true);
      setError(null);
      const cropped = await cropScanImage(preview.localUri, (size) =>
        regionToContainedImageCrop(region, previewFrame, size.width, size.height),
      );
      deliverCrop(
        { localUri: cropped.uri, contentType: "image/jpeg", fileName: preview.fileName, kind: "image" },
        shotSubject,
        isCurrent,
      );
    });
  }, [busy, crop, deliverCrop, preview, previewFrame, runShot]);

  /** Back to the live camera, by Retake or Android Back (held while Solve cuts the shot); the last shot's files are deleted. */
  const retake = useCallback(() => {
    if (busy) return;
    files.discardAll();
    resetLive();
    crop.resetRegion();
    setPreview(null);
    setError(null);
  }, [busy, crop, files, resetLive]);

  const changeSubject = useCallback((next: ScannerSubject) => {
    if (next === subject) return;
    const currentIndex = SCANNER_SUBJECTS.indexOf(next);
    const previousIndex = SCANNER_SUBJECTS.indexOf(subject);
    selection();
    void playScannerSwitchCue(currentIndex > previousIndex ? 1 : -1);
    resetLive();
    setSubject(next);
  }, [resetLive, subject]);

  /** Photos by default (no permission needed, and where a homework photo is); Files second. */
  const openLibrary = useCallback(async (source: "photos" | "files") => {
    if (busy) return;
    const shotSubject = subject;
    const session = sessionRef.current;
    const isCurrent = () => session === sessionRef.current;
    setBusy(true);
    setError(null);
    try {
      await scheduleIdlePromise();
      const picked = await (source === "files" ? pickImageDocument() : pickFromPhotoLibrary());
      if (!picked) return;
      // The picker copied the image into the cache for the scanner.
      files.track(picked.localUri);
      if (isCurrent()) resetLive();
      await showShot(picked, shotSubject, isCurrent);
    } catch (caught) {
      if (!isCurrent()) return;
      if (caught instanceof NativePickerBusyError || caught instanceof NativePickerTimeoutError) {
        setError(t("chat.picker_busy"));
      } else {
        setError(t("chat.math_scan_failed"));
      }
    } finally {
      setBusy(false);
    }
  }, [busy, files, resetLive, showShot, subject, t]);

  const cameraOff = cameraStatus.kind === "unavailable";
  const choosePhoto = () => void openLibrary("photos");

  if (!hosted && !visible) return null;

  return (
    <FullScreenModal
      visible={visible}
      animationType="fade"
      presentationStyle="fullScreen"
      statusBarTranslucent
      onRequestClose={preview ? retake : onClose}
      onDismiss={() => setHosted(false)}
      testID="math-scanner-modal"
    >
      <GestureHandlerRootView style={s.root} onLayout={handleLayout}>
        {!permission && !preview ? (
          <View style={s.center}>
            <ActivityIndicator color={theme.onMedia} />
          </View>
        ) : !granted && !preview ? (
          <ScannerPermission
            permission={permission}
            requestPermission={() => void requestPermission()}
            onChoosePhoto={choosePhoto}
            onChooseFile={() => void openLibrary("files")}
          />
        ) : (
          <View style={StyleSheet.absoluteFill} collapsable={false}>
            {granted ? <View style={StyleSheet.absoluteFill} testID="math-scanner-camera" pointerEvents="none">
              <LiveMathScannerCamera
                ref={cameraRef}
                active={!preview && visible}
                torchOn={torchOn && !preview && visible}
                zoom={zoom}
                scanRegion={scanRegion}
                viewSize={view}
                subject={subject}
                readEpoch={readEpoch}
                onReady={camera.onReady}
                onError={camera.onError}
                onUnavailable={camera.onUnavailable}
                onDetectionChange={handleLiveDetection}
              />
            </View> : null}
            {granted && !preview && cameraStatus.kind === "ready" ? (
              <ScannerFocusArea gesture={focus.tapGesture} inset={inset} viewHeight={view.height} />
            ) : null}
            {granted && !preview && cameraStatus.kind === "unavailable" ? (
              <ScannerCameraUnavailable reason={cameraStatus.reason} onChoosePhoto={choosePhoto} />
            ) : null}
            {preview ? <ScannerPreviewImage uri={preview.localUri} frame={previewFrame} view={view} /> : null}
            {preview || (granted && !cameraOff) ? (
              <MathScannerCropOverlay
                regionGesture={crop.regionGesture}
                handles={crop.handles}
                regionStyle={crop.regionStyle}
                maskTopStyle={crop.maskTopStyle}
                maskBottomStyle={crop.maskBottomStyle}
                maskLeftStyle={crop.maskLeftStyle}
                maskRightStyle={crop.maskRightStyle}
                scanning={Boolean(preview) && !busy}
                liveStatus={preview ? "idle" : liveStatus}
                onGrow={crop.growRegion}
                onShrink={crop.shrinkRegion}
              />
            ) : null}
            <ScannerFocusRing point={focus.focusPoint} />
          </View>
        )}
        <MathScannerChrome
          insets={insets}
          granted={granted}
          preview={Boolean(preview)}
          busy={busy}
          capturing={capturing}
          camera={cameraStatus.kind}
          torchOn={torchOn}
          subject={subject}
          error={error}
          onClose={onClose}
          onSubjectChange={changeSubject}
          onToggleTorch={() => {
            selection();
            setTorchOn((on) => !on);
          }}
          onOpenPhotos={() => void openLibrary("photos")}
          onOpenFiles={() => void openLibrary("files")}
          onCapture={capture}
          onRetake={retake}
          onSolve={confirmPreview}
        />
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
  });
}
