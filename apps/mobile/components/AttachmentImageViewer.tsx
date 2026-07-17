import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  Modal,
  Pressable,
  StyleSheet,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/contexts/AuthContext";
import { downloadChatAttachment } from "@/lib/downloadChatAttachment";
import { getApiUrl } from "@/lib/config";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  visible: boolean;
  onClose: () => void;
  attachmentId?: string | null;
  localUri?: string | null;
  path?: string | null;
  fileName?: string;
};

const SHEET_RADIUS = 26;

export function AttachmentImageViewer({
  visible,
  onClose,
  attachmentId,
  localUri,
  path,
  fileName = "image.jpg",
}: Props) {
  const C = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(C), [C]);
  const { token } = useAuth();
  const insets = useSafeAreaInsets();
  const [failed, setFailed] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const remoteUri = useMemo(() => {
    if (localUri) return localUri;
    if (attachmentId) return `${getApiUrl()}/attachments/${attachmentId}/file`;
    if (path?.startsWith("http://") || path?.startsWith("https://")) return path;
    if (path?.startsWith("/attachments/")) return `${getApiUrl()}${path}`;
    return null;
  }, [attachmentId, localUri, path]);

  useEffect(() => {
    if (visible) setFailed(false);
  }, [visible, remoteUri]);

  const source =
    token && attachmentId && !localUri && remoteUri
      ? { uri: remoteUri, headers: { Authorization: `Bearer ${token}` } }
      : remoteUri
        ? { uri: remoteUri }
        : null;

  const handleDownload = async () => {
    if (!remoteUri || downloading) return;
    setDownloading(true);
    try {
      await downloadChatAttachment({
        uri: remoteUri,
        token,
        fileName,
      });
    } catch (error) {
      Alert.alert(
        t("common.download_failed"),
        error instanceof Error ? error.message : t("common.download_image_error"),
      );
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={s.backdrop}>
        <Pressable
          style={[s.scrim, { height: Math.max(insets.top + 10, 28) }]}
          onPress={onClose}
          accessibilityLabel={t("preview.close")}
        />

        <View style={[s.sheet, { paddingBottom: insets.bottom }]}>
          <View style={s.header}>
            <Pressable
              style={s.iconBtn}
              onPress={onClose}
              hitSlop={12}
              accessibilityLabel={t("preview.close")}
            >
              <Ionicons name="close" size={28} color={C.text} />
            </Pressable>

            <Pressable
              style={[s.iconBtn, downloading && s.iconBtnDisabled]}
              onPress={handleDownload}
              disabled={!remoteUri || downloading}
              hitSlop={12}
              accessibilityLabel={t("common.download")}
            >
              {downloading ? (
                <ActivityIndicator color={C.text} size="small" />
              ) : (
                <Ionicons name="download-outline" size={24} color={C.text} />
              )}
            </Pressable>
          </View>

          <View style={s.stage}>
            {!source || failed ? (
              <ActivityIndicator color={C.textTertiary} size="large" />
            ) : (
              <Image
                source={source}
                style={s.image}
                resizeMode="contain"
                onError={() => setFailed(true)}
              />
            )}
          </View>
        </View>
      </View>
    </Modal>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    backdrop: {
      flex: 1,
      backgroundColor: C.isDark ? "#1A1A1A" : "#525252",
    },
    scrim: {
      width: "100%",
    },
    sheet: {
      flex: 1,
      backgroundColor: C.bg,
      borderTopLeftRadius: SHEET_RADIUS,
      borderTopRightRadius: SHEET_RADIUS,
      overflow: "hidden",
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: 12,
      paddingTop: 8,
      paddingBottom: 4,
    },
    iconBtn: {
      width: 44,
      height: 44,
      alignItems: "center",
      justifyContent: "center",
    },
    iconBtnDisabled: {
      opacity: 0.45,
    },
    stage: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
    },
    image: {
      width: "100%",
      height: "100%",
    },
  });
}
