import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
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
import { Gesture, GestureDetector, GestureHandlerRootView } from "react-native-gesture-handler";
import { runOnJS } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { MathScanConfirmView } from "@/components/MathScanConfirmView";
import { extractMathScan } from "@/lib/api/mathScan";
import type { PendingAttachment } from "@/lib/attachments";
import { HeicUnsupportedError, pickFromPhotoLibrary } from "@/lib/attachments";
import { cameraPermissionNeedsSettings } from "@/lib/cameraPermission";
import {
  clampScanRegion,
  defaultScanRegion,
  regionIsDefault,
  regionToImageCrop,
  resizeScanRegionFromCorner,
  translateScanRegion,
  zoomFromPinch,
  type ScanCorner,
  type ScanRegion,
} from "@/lib/math/mathScannerRegion";
import { Theme, useTheme, withAlpha } from "@/lib/theme";
import { IconSize } from "@/lib/icons";

type Props = {
  visible: boolean;
  token: string | null;
  onClose: () => void;
  onCaptured: (pending: PendingAttachment, options?: { confirmedReading?: string }) => void;
};

type OcrStatus = "idle" | "loading" | "done" | "failed";

const HANDLE = 44;
const FOCUS_MS = 900;

/**
 * In-app equation scanner: live rear camera, pinch-to-zoom, torch, and a
 * free-form crop with corner handles. OCR starts on the cropped preview so
 * the student can confirm the reading before Solve.
 */
export function MathEquationScanner({ visible, token, onClose, onCaptured }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { width: windowWidth, height: windowHeight } = useWindowDimensions();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<PendingAttachment | null>(null);
  const [region, setRegion] = useState<ScanRegion>(defaultScanRegion());
  const [torchOn, setTorchOn] = useState(false);
  const [zoom, setZoom] = useState(0);
  const [autofocus, setAutofocus] = useState<"on" | "off">("off");
  const [focusPoint, setFocusPoint] = useState<{ x: number; y: number } | null>(null);
  const [ocrStatus, setOcrStatus] = useState<OcrStatus>("idle");
  const [reading, setReading] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const [solveWaiting, setSolveWaiting] = useState(false);
  const regionRef = useRef(region);
  regionRef.current = region;
  const zoomRef = useRef(zoom);
  zoomRef.current = zoom;
  const pinchStartZoomRef = useRef(0);
  const panBaseRef = useRef(region);
  const cornerBaseRef = useRef(region);
  const extractGenRef = useRef(0);
  const extractAbortRef = useRef<AbortController | null>(null);
  const focusTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const resetLive = useCallback(() => {
    extractGenRef.current += 1;
    extractAbortRef.current?.abort();
    extractAbortRef.current = null;
    setPreview(null);
    setError(null);
    setOcrStatus("idle");
    setReading("");
    setUncertain(false);
    setSolveWaiting(false);
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
      extractAbortRef.current?.abort();
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
  }, []);
  const applyPinch = useCallback((scale: number) => {
    setZoom(zoomFromPinch(pinchStartZoomRef.current, scale));
  }, []);

  const onFocusTap = useCallback((x: number, y: number) => {
    setFocusPoint({ x, y });
    setAutofocus("on");
    if (focusTimerRef.current) clearTimeout(focusTimerRef.current);
    focusTimerRef.current = setTimeout(() => {
      setAutofocus("off");
      setFocusPoint(null);
    }, FOCUS_MS);
  }, []);

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
      Gesture.Tap().onEnd((e) => {
        runOnJS(onFocusTap)(e.x, e.y);
      }),
    [onFocusTap],
  );
  const cameraGesture = useMemo(
    () => Gesture.Simultaneous(pinchGesture, tapGesture),
    [pinchGesture, tapGesture],
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
  const regionRight = regionLeft + regionWidth;
  const regionBottom = regionTop + regionHeight;
  const regionDirty = !regionIsDefault(region);

  const startOcr = useCallback(
    (pending: PendingAttachment) => {
      extractGenRef.current += 1;
      const gen = extractGenRef.current;
      extractAbortRef.current?.abort();
      const controller = new AbortController();
      extractAbortRef.current = controller;
      setOcrStatus("loading");
      setReading("");
      setUncertain(false);
      if (!token) {
        setOcrStatus("failed");
        return;
      }
      void extractMathScan(token, pending, controller.signal)
        .then((result) => {
          if (gen !== extractGenRef.current) return;
          const text = result.display_text.trim();
          setReading(text);
          setUncertain(result.uncertain);
          setOcrStatus(text ? "done" : "failed");
        })
        .catch(() => {
          if (gen !== extractGenRef.current) return;
          setOcrStatus("failed");
        });
    },
    [token],
  );

  const showPreview = useCallback(
    (pending: PendingAttachment) => {
      setPreview(pending);
      startOcr(pending);
    },
    [startOcr],
  );

  const capture = useCallback(async () => {
    if (!cameraRef.current || busy) return;
    setBusy(true);
    setError(null);
    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.9,
        shutterSound: false,
        exif: true,
      });
      if (!photo?.uri) {
        setError(t("chat.math_scan_failed"));
        return;
      }

      const imageWidth = photo.width ?? 0;
      const imageHeight = photo.height ?? 0;
      if (!imageWidth || !imageHeight) {
        showPreview({
          localUri: photo.uri,
          contentType: "image/jpeg",
          fileName: `math-scan-${Date.now()}.jpg`,
          kind: "image",
        });
        return;
      }

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
      showPreview({
        localUri: result.uri,
        contentType: "image/jpeg",
        fileName: `math-scan-${Date.now()}.jpg`,
        kind: "image",
      });
    } catch {
      setError(t("chat.math_scan_failed"));
    } finally {
      setBusy(false);
    }
  }, [busy, showPreview, t, windowWidth, windowHeight]);

  const closeScanner = useCallback(() => {
    resetLive();
    onClose();
  }, [onClose, resetLive]);

  const confirmPreview = useCallback(() => {
    if (!preview) return;
    if (ocrStatus === "loading") {
      setSolveWaiting(true);
      return;
    }
    onCaptured(preview, { confirmedReading: reading });
    resetLive();
  }, [ocrStatus, onCaptured, preview, reading, resetLive]);

  useEffect(() => {
    if (!solveWaiting || ocrStatus === "loading" || !preview) return;
    onCaptured(preview, { confirmedReading: reading });
    resetLive();
  }, [ocrStatus, onCaptured, preview, reading, resetLive, solveWaiting]);

  const retakePreview = useCallback(() => {
    extractGenRef.current += 1;
    extractAbortRef.current?.abort();
    setPreview(null);
    setError(null);
    setOcrStatus("idle");
    setReading("");
    setUncertain(false);
    setSolveWaiting(false);
  }, []);

  const resetRegion = useCallback(() => {
    setRegion(clampScanRegion(defaultScanRegion()));
  }, []);

  const openLibrary = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const picked = await pickFromPhotoLibrary();
      if (picked) showPreview(picked);
    } catch (error) {
      if (error instanceof HeicUnsupportedError) {
        setError(t("chat.heic_unsupported_body"));
      } else {
        setError(error instanceof Error ? error.message : t("chat.math_scan_failed"));
      }
    } finally {
      setBusy(false);
    }
  }, [busy, showPreview, t]);

  const granted = Boolean(permission?.granted);
  const cameraLayer = !permission ? (
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
    <GestureDetector gesture={cameraGesture}>
      <View style={StyleSheet.absoluteFill} collapsable={false}>
        <CameraView
          ref={cameraRef}
          style={StyleSheet.absoluteFill}
          facing="back"
          mode="picture"
          zoom={zoom}
          enableTorch={torchOn}
          flash="off"
          autofocus={autofocus}
        />
        <View style={s.maskLayer} pointerEvents="none">
          <View style={[s.mask, { top: 0, left: 0, right: 0, height: regionTop }]} />
          <View style={[s.mask, { top: regionBottom, left: 0, right: 0, bottom: 0 }]} />
          <View
            style={[s.mask, { top: regionTop, left: 0, width: regionLeft, height: regionHeight }]}
          />
          <View
            style={[s.mask, { top: regionTop, left: regionRight, right: 0, height: regionHeight }]}
          />
        </View>
        <GestureDetector gesture={panGesture}>
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
          </View>
        </GestureDetector>
        <GestureDetector gesture={cornerTL}>
          <View style={[s.handle, { left: regionLeft - HANDLE / 2, top: regionTop - HANDLE / 2 }]} />
        </GestureDetector>
        <GestureDetector gesture={cornerTR}>
          <View
            style={[s.handle, { left: regionRight - HANDLE / 2, top: regionTop - HANDLE / 2 }]}
          />
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
        {focusPoint ? (
          <View
            pointerEvents="none"
            style={[s.focusSquare, { left: focusPoint.x - 36, top: focusPoint.y - 36 }]}
          />
        ) : null}
      </View>
    </GestureDetector>
  );

  const overlay = (
    <>
      <Pressable
        style={[s.close, { top: insets.top + 8 }]}
        onPress={closeScanner}
        hitSlop={12}
        accessibilityRole="button"
        accessibilityLabel={t("common.close")}
      >
        <Icon name="close" size={28} color={theme.onMedia} />
      </Pressable>
      {granted ? (
        <Pressable
          style={[s.torchBtn, { top: insets.top + 8 }]}
          onPress={() => setTorchOn((on) => !on)}
          hitSlop={10}
          accessibilityRole="button"
          accessibilityState={{ selected: torchOn }}
          accessibilityLabel={
            torchOn ? t("chat.math_scan_torch_on_a11y") : t("chat.math_scan_torch_off_a11y")
          }
        >
          <Icon
            name={torchOn ? "flashlight" : "flashlight-outline"}
            size={IconSize.md}
            color={theme.onMedia}
          />
        </Pressable>
      ) : null}
      {granted && regionDirty ? (
        <Pressable
          style={[s.resetBtn, { top: insets.top + 56 }]}
          onPress={resetRegion}
          hitSlop={10}
          accessibilityRole="button"
          accessibilityLabel={t("chat.math_scan_reset_a11y")}
        >
          <Icon name="scan-outline" size={IconSize.sm} color={theme.onMedia} />
        </Pressable>
      ) : null}
      {granted ? (
        <View style={[s.hintWrap, { top: insets.top + (regionDirty ? 104 : 56) }]}>
          <Text style={s.hint}>{t("chat.math_scan_hint")}</Text>
        </View>
      ) : null}
      {error ? <Text style={s.error}>{error}</Text> : null}
      {granted ? (
        <View style={[s.controls, { paddingBottom: Math.max(insets.bottom, 16) + 12 }]}>
          <Pressable
            style={s.photosBtn}
            onPress={() => void openLibrary()}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel={t("chat.math_scan_photos_a11y")}
          >
            <Icon name="images-outline" size={26} color={theme.onMedia} />
            <Text style={s.photosLabel}>{t("chat.math_scan_photos")}</Text>
          </Pressable>
          <Pressable
            style={s.shutter}
            onPress={() => void capture()}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel={t("chat.math_scan_capture_a11y")}
          >
            {busy ? <ActivityIndicator color={theme.text} /> : <View style={s.shutterInner} />}
          </Pressable>
          <View style={s.photosBtn} />
        </View>
      ) : null}
    </>
  );

  if (!visible) return null;

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={closeScanner}>
      <GestureHandlerRootView style={s.root}>
        {preview ? (
          <MathScanConfirmView
            preview={preview}
            ocrStatus={ocrStatus}
            reading={reading}
            uncertain={uncertain}
            onChangeReading={setReading}
            onClose={closeScanner}
            onRetake={retakePreview}
            onSolve={confirmPreview}
            solveWaiting={solveWaiting}
            theme={theme}
          />
        ) : (
          <>
            <View style={s.cameraLayer}>{cameraLayer}</View>
            <View style={s.overlayLayer} pointerEvents="box-none">
              {overlay}
            </View>
          </>
        )}
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
      backgroundColor: withAlpha(theme.mediaScrim, 0.55),
    },
    torchBtn: {
      position: "absolute",
      right: 16,
      width: 40,
      height: 40,
      borderRadius: 20,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: withAlpha(theme.mediaScrim, 0.55),
    },
    resetBtn: {
      position: "absolute",
      right: 16,
      width: 40,
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
      width: 72,
      height: 72,
      borderWidth: 1.5,
      borderColor: theme.onMedia,
      borderRadius: 8,
    },
    hintWrap: {
      position: "absolute",
      alignSelf: "center",
      backgroundColor: withAlpha(theme.mediaScrim, 0.55),
      borderRadius: 14,
      paddingHorizontal: 14,
      paddingVertical: 7,
      zIndex: 10,
    },
    hint: {
      color: theme.onMedia,
      fontSize: 14,
      fontWeight: "600",
      textAlign: "center",
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
