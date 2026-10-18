import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useTranslation } from "react-i18next";

import { useAuthToken } from "@/contexts/AuthContext";
import {
  AttachmentViewerChrome,
  type AttachmentViewerProps,
} from "@/features/attachments/components/AttachmentViewerChrome";
import { resolveAttachmentUri } from "@/features/attachments/model/attachmentUri";
import { fetchAttachmentBase64 } from "@/features/attachments/model/fetchAttachmentBytes";
import { buildPdfPreviewHtml } from "@/lib/pdfPreviewHtml";
import { Theme, useTheme } from "@/lib/theme";
import { Space } from "@/lib/space";
import { Type, Weight } from "@/lib/type";
import {
  getPreviewWebView,
  STATIC_HTML_ORIGIN_WHITELIST,
  useStaticOnlyNavigation,
} from "@/lib/webView";

type Props = AttachmentViewerProps & {
  attachmentId?: string | null;
  localUri?: string | null;
  path?: string | null;
};

export function AttachmentPdfViewer({ visible, attachmentId, localUri, path, ...chrome }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeViewerStyles(theme), [theme]);
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
    <AttachmentViewerChrome
      {...chrome}
      visible={visible}
      closeLabel={t("chat.pdf_close_a11y")}
      shareLabel={t("chat.pdf_share_a11y")}
    >
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
    </AttachmentViewerChrome>
  );
}

function makeViewerStyles(t: Theme) {
  return StyleSheet.create({
    body: { flex: 1, alignItems: "center", justifyContent: "center" },
    webview: { flex: 1, width: "100%", backgroundColor: t.bg },
    error: { ...Type.callout, ...Weight.regular, color: t.textSecondary, paddingHorizontal: Space.lg, textAlign: "center" },
  });
}
