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
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import type { PendingAttachment } from "@/lib/attachments";
import { Theme, useTheme } from "@/lib/theme";

/** Fraction of the preview height used as the equation scan band. */
const BAND_HEIGHT_RATIO = 0.22;

type Props = {
  visible: boolean;
  onClose: () => void;
  onCaptured: (pending: PendingAttachment) => void;
};

/**
 * In-app equation scanner: live camera with a horizontal crop guide.
 * Captures only the band (not the whole frame) so OCR sees the equation.
 */
export function MathEquationScanner({ visible, onClose, onCaptured }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { height: windowHeight } = useWindowDimensions();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const bandHeight = Math.round(windowHeight * BAND_HEIGHT_RATIO);
  const bandTop = Math.round((windowHeight - bandHeight) / 2);

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

      // CameraView uses cover-style fill; map the on-screen band into image
      // coordinates assuming the preview covers the full window height.
      const originY = Math.max(0, Math.round((bandTop / windowHeight) * imageHeight));
      const cropHeight = Math.min(
        imageHeight - originY,
        Math.round((bandHeight / windowHeight) * imageHeight),
      );
      const result = await ImageManipulator.manipulateAsync(
        photo.uri,
        [
          {
            crop: {
              originX: 0,
              originY,
              width: imageWidth,
              height: Math.max(1, cropHeight),
            },
          },
        ],
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
  }, [bandHeight, bandTop, busy, onCaptured, onClose, t, windowHeight]);

  if (!visible) return null;

  const body = !permission ? (
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
      <View style={s.overlay} pointerEvents="none">
        <View style={[s.mask, { height: bandTop }]} />
        <View style={[s.band, { height: bandHeight }]}>
          <View style={s.bandCornerTL} />
          <View style={s.bandCornerTR} />
          <View style={s.bandCornerBL} />
          <View style={s.bandCornerBR} />
        </View>
        <View style={[s.mask, { flex: 1 }]} />
      </View>
      <Text style={[s.hint, { top: insets.top + 56 }]}>{t("chat.math_scan_hint")}</Text>
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

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={s.root}>
        <Pressable
          style={[s.close, { top: insets.top + 8 }]}
          onPress={onClose}
          hitSlop={12}
          accessibilityRole="button"
          accessibilityLabel={t("common.close")}
        >
          <Ionicons name="close" size={28} color="#fff" />
        </Pressable>
        {body}
      </View>
    </Modal>
  );
}

function makeStyles(theme: Theme) {
  const corner = {
    position: "absolute" as const,
    width: 22,
    height: 22,
    borderColor: "#FFFFFF",
  };
  return StyleSheet.create({
    root: {
      flex: 1,
      backgroundColor: "#000",
    },
    close: {
      position: "absolute",
      left: 16,
      zIndex: 20,
      width: 40,
      height: 40,
      borderRadius: 20,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: "rgba(0,0,0,0.45)",
    },
    overlay: {
      ...StyleSheet.absoluteFill,
      justifyContent: "flex-start",
    },
    mask: {
      backgroundColor: "rgba(0,0,0,0.55)",
      width: "100%",
    },
    band: {
      width: "100%",
      borderColor: "rgba(255,255,255,0.85)",
      borderTopWidth: StyleSheet.hairlineWidth,
      borderBottomWidth: StyleSheet.hairlineWidth,
      backgroundColor: "transparent",
    },
    bandCornerTL: { ...corner, top: 0, left: 16, borderTopWidth: 3, borderLeftWidth: 3 },
    bandCornerTR: { ...corner, top: 0, right: 16, borderTopWidth: 3, borderRightWidth: 3 },
    bandCornerBL: { ...corner, bottom: 0, left: 16, borderBottomWidth: 3, borderLeftWidth: 3 },
    bandCornerBR: { ...corner, bottom: 0, right: 16, borderBottomWidth: 3, borderRightWidth: 3 },
    hint: {
      position: "absolute",
      alignSelf: "center",
      color: "#fff",
      fontSize: 15,
      fontWeight: "600",
      textAlign: "center",
      paddingHorizontal: 24,
      textShadowColor: "rgba(0,0,0,0.6)",
      textShadowRadius: 6,
      zIndex: 10,
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
      width: 74,
      height: 74,
      borderRadius: 37,
      borderWidth: 4,
      borderColor: "#fff",
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: "rgba(255,255,255,0.15)",
    },
    shutterInner: {
      width: 58,
      height: 58,
      borderRadius: 29,
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
