import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useTranslation } from "react-i18next";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Icon } from "@/components/Icon";
import { useAuthToken } from "@/contexts/AuthContext";
import { resolveAttachmentUri } from "@/lib/attachmentUri";
import { fetchAttachmentBytes } from "@/lib/fetchAttachmentBytes";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

const MAX_PREVIEW_CHARS = 200_000;

type Props = {
  visible: boolean;
  onClose: () => void;
  attachmentId?: string | null;
  path?: string | null;
  fileName: string;
  onShare: () => void;
};

export function AttachmentTextViewer({
  visible,
  onClose,
  attachmentId,
  path,
  fileName,
  onShare,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const token = useAuthToken();
  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);

  const remoteUri = useMemo(
    () => resolveAttachmentUri({ attachmentId, path }),
    [attachmentId, path],
  );

  useEffect(() => {
    if (!visible || !remoteUri) {
      setText(null);
      setFailed(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setFailed(false);
    void (async () => {
      try {
        const bytes = await fetchAttachmentBytes(remoteUri, token);
        if (cancelled) return;
        const decoded = new TextDecoder("utf-8", { fatal: false }).decode(bytes);
        setText(decoded.length > MAX_PREVIEW_CHARS ? decoded.slice(0, MAX_PREVIEW_CHARS) : decoded);
      } catch {
        if (!cancelled) setFailed(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [visible, remoteUri, token]);

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={[s.root, { paddingTop: insets.top, paddingBottom: insets.bottom }]}>
        <View style={s.toolbar}>
          <Pressable onPress={onClose} hitSlop={8} accessibilityLabel={t("preview.close")}>
            <Icon name="close" size={24} color={theme.text} />
          </Pressable>
          <Text style={s.title} numberOfLines={1}>
            {fileName}
          </Text>
          <Pressable onPress={onShare} hitSlop={8} accessibilityLabel={t("preview.share")}>
            <Icon name="share-outline" size={22} color={theme.primary} />
          </Pressable>
        </View>
        <View style={s.body}>
          {loading ? (
            <ActivityIndicator color={theme.primary} size="large" />
          ) : failed || text == null ? (
            <Text style={s.error}>{t("gallery.file_preview_failed")}</Text>
          ) : (
            <ScrollView
              testID="attachment-text-preview"
              contentContainerStyle={s.scroll}
            >
              <Text style={s.fileText} selectable>
                {text}
              </Text>
            </ScrollView>
          )}
        </View>
      </View>
    </Modal>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: t.bg },
    toolbar: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
    },
    title: { flex: 1, fontSize: 16, fontWeight: "600", color: t.text },
    body: { flex: 1 },
    scroll: { padding: Space.md },
    fileText: { ...Type.body, color: t.text },
    error: {
      ...Type.body,
      color: t.textSecondary,
      paddingHorizontal: Space.lg,
      textAlign: "center",
      marginTop: Space.xl,
    },
  });
}
