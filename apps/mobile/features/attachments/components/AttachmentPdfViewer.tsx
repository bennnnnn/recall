import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useTranslation } from "react-i18next";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { IconButton } from "@/components/IconButton";
import { useAuthToken } from "@/contexts/AuthContext";
import { resolveAttachmentUri } from "@/features/attachments/model/attachmentUri";
import { fetchAttachmentBase64 } from "@/features/attachments/model/fetchAttachmentBytes";
import { buildPdfPreviewHtml } from "@/lib/pdfPreviewHtml";
import { IconSize } from "@/lib/icons";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import {
  getPreviewWebView,
  STATIC_HTML_ORIGIN_WHITELIST,
  useStaticOnlyNavigation,
} from "@/lib/webView";

type Props = {
  visible: boolean;
  onClose: () => void;
  attachmentId?: string | null;
  localUri?: string | null;
  path?: string | null;
  fileName: string;
  onShare: () => void;
};

export function AttachmentPdfViewer({
  visible,
  onClose,
  attachmentId,
  localUri,
  path,
  fileName,
  onShare,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeViewerStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const token = useAuthToken();
  const [html, setHtml] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);

  const remoteUri = useMemo(
    () => resolveAttachmentUri({ attachmentId, localUri, path }),
    [attachmentId, localUri, path],
  );

  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const onShouldStartLoadWithRequest = useStaticOnlyNavigation(html);

  useEffect(() => {
    if (!visible || !remoteUri) {
      setHtml(null);
      setFailed(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setFailed(false);
    void (async () => {
      try {
        const b64 = await fetchAttachmentBase64(remoteUri, token);
        if (!cancelled) setHtml(buildPdfPreviewHtml(b64, theme));
      } catch {
        if (!cancelled) setFailed(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [visible, remoteUri, token, theme]);

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={[s.root, { paddingTop: insets.top, paddingBottom: insets.bottom }]}>
        <View style={s.toolbar}>
          <IconButton
            onPress={onClose}
            accessibilityLabel={t("chat.pdf_close_a11y")}
            name="close"
            size={IconSize.lg}
            color={theme.text}
          />
          <Text style={s.title} numberOfLines={1}>
            {fileName}
          </Text>
          <IconButton
            onPress={onShare}
            accessibilityLabel={t("chat.pdf_share_a11y")}
            name="share-outline"
            size={IconSize.md}
            color={theme.primary}
          />
        </View>
        <View style={s.body}>
          {loading ? (
            <ActivityIndicator color={theme.primary} size="large" />
          ) : failed || !WebView || !html ? (
            <Text style={s.error}>{t("chat.pdf_preview_failed")}</Text>
          ) : (
            <WebView
              originWhitelist={STATIC_HTML_ORIGIN_WHITELIST}
              source={{ html }}
              style={s.webview}
              javaScriptEnabled
              onShouldStartLoadWithRequest={onShouldStartLoadWithRequest}
            />
          )}
        </View>
      </View>
    </Modal>
  );
}

function makeViewerStyles(t: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: t.bg },
    toolbar: {
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      paddingHorizontal: 16,
      paddingVertical: 12,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
    },
    title: { flex: 1, ...Type.body, fontWeight: "600", color: t.text },
    body: { flex: 1, alignItems: "center", justifyContent: "center" },
    webview: { flex: 1, width: "100%", backgroundColor: t.bg },
    error: { ...Type.callout, fontWeight: "400", color: t.textSecondary, paddingHorizontal: 24, textAlign: "center" },
  });
}
