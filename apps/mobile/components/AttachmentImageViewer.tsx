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

import { useAuthToken } from "@/contexts/AuthContext";
import {
  ensureLocalAttachmentFile,
  getCachedAttachmentFile,
  saveChatAttachmentToLibrary,
  shareChatAttachment,
} from "@/lib/downloadChatAttachment";
import { getApiUrl } from "@/lib/config";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  visible: boolean;
  onClose: () => void;
  attachmentId?: string | null;
  localUri?: string | null;
  path?: string | null;
  fileName?: string;
  /** Already-resolved display URI from the chat thumbnail (instant open). */
  previewUri?: string | null;
};

const SHEET_RADIUS = 26;

export function AttachmentImageViewer({
  visible,
  onClose,
  attachmentId,
  localUri,
  path,
  fileName = "image.jpg",
  previewUri = null,
}: Props) {
  const C = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(C), [C]);
  const token = useAuthToken();
  const insets = useSafeAreaInsets();
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState<"download" | "share" | null>(null);
  const [cachedUri, setCachedUri] = useState<string | null>(null);

  const remoteUri = useMemo(() => {
    if (localUri) return localUri;
    if (attachmentId) return `${getApiUrl()}/attachments/${attachmentId}/file`;
    if (path?.startsWith("http://") || path?.startsWith("https://")) return path;
    if (path?.startsWith("/attachments/")) return `${getApiUrl()}${path}`;
    return null;
  }, [attachmentId, localUri, path]);

  // Prefer local file / in-memory cache / thumbnail URI so the large view
  // paints immediately instead of waiting on a second authenticated fetch.
  const displayUri =
    cachedUri ||
    (remoteUri ? getCachedAttachmentFile(remoteUri) : null) ||
    localUri ||
    previewUri ||
    remoteUri;

  useEffect(() => {
    if (!visible) return;
    setFailed(false);
    if (!remoteUri) return;

    const existing = getCachedAttachmentFile(remoteUri) || localUri;
    if (existing) {
      setCachedUri(existing);
      return;
    }

    let cancelled = false;
    void ensureLocalAttachmentFile({
      uri: remoteUri,
      token,
      fileName,
    })
      .then((uri) => {
        if (!cancelled) setCachedUri(uri);
      })
      .catch(() => {
        // Keep showing previewUri / remote; download/share will surface errors.
      });
    return () => {
      cancelled = true;
    };
  }, [visible, remoteUri, localUri, token, fileName]);

  const source = useMemo(() => {
    if (!displayUri) return null;
    if (
      token &&
      attachmentId &&
      !localUri &&
      !cachedUri &&
      displayUri.startsWith("http")
    ) {
      return { uri: displayUri, headers: { Authorization: `Bearer ${token}` } };
    }
    return { uri: displayUri };
  }, [displayUri, token, attachmentId, localUri, cachedUri]);

  const handleDownload = async () => {
    if (!remoteUri || busy) return;
    setBusy("download");
    try {
      const result = await saveChatAttachmentToLibrary({
        uri: remoteUri,
        token,
        fileName,
      });
      if (result === "saved") {
        Alert.alert(t("common.saved"), t("common.saved_to_photos"));
      }
    } catch (error) {
      Alert.alert(
        t("common.download_failed"),
        error instanceof Error ? error.message : t("common.download_image_error"),
      );
    } finally {
      setBusy(null);
    }
  };

  const handleShare = async () => {
    if (!remoteUri || busy) return;
    setBusy("share");
    try {
      await shareChatAttachment({
        uri: remoteUri,
        token,
        fileName,
      });
    } catch (error) {
      Alert.alert(
        t("common.share_failed"),
        error instanceof Error ? error.message : t("common.share_image_error"),
      );
    } finally {
      setBusy(null);
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

            <View style={s.headerActions}>
              <Pressable
                style={[s.iconBtn, busy === "share" && s.iconBtnDisabled]}
                onPress={() => void handleShare()}
                disabled={!remoteUri || busy != null}
                hitSlop={12}
                accessibilityLabel={t("preview.share")}
              >
                {busy === "share" ? (
                  <ActivityIndicator color={C.text} size="small" />
                ) : (
                  <Ionicons name="share-outline" size={24} color={C.text} />
                )}
              </Pressable>
              <Pressable
                style={[s.iconBtn, busy === "download" && s.iconBtnDisabled]}
                onPress={() => void handleDownload()}
                disabled={!remoteUri || busy != null}
                hitSlop={12}
                accessibilityLabel={t("common.download")}
              >
                {busy === "download" ? (
                  <ActivityIndicator color={C.text} size="small" />
                ) : (
                  <Ionicons name="download-outline" size={24} color={C.text} />
                )}
              </Pressable>
            </View>
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
      backgroundColor: C.scrim,
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
    headerActions: {
      flexDirection: "row",
      alignItems: "center",
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
