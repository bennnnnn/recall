import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useTranslation } from "react-i18next";

import { AttachmentPdfViewer } from "@/components/AttachmentPdfViewer";
import { Icon } from "@/components/Icon";

import { useAuthToken } from "@/contexts/AuthContext";
import { useAttachmentIndexed } from "@/hooks/useAttachmentIndexed";
import { useDeferredWebViewMount } from "@/hooks/useDeferredWebViewMount";
import { resolveAttachmentUri } from "@/lib/attachmentUri";
import { downloadChatAttachment } from "@/lib/downloadChatAttachment";
import { fetchAttachmentBase64 } from "@/lib/fetchAttachmentBytes";
import { buildPdfPreviewHtml } from "@/lib/pdfPreviewHtml";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import {
  getPreviewWebView,
  STATIC_HTML_ORIGIN_WHITELIST,
  useStaticOnlyNavigation,
} from "@/lib/webView";

type Props = {
  attachmentId?: string | null;
  localUri?: string | null;
  path?: string | null;
  fileName?: string;
  compact?: boolean;
};

export function ChatMessagePdf({
  attachmentId,
  localUri,
  path,
  fileName = "document.pdf",
  compact = false,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme, compact), [theme, compact]);
  const token = useAuthToken();
  const { indexed, failed: indexFailed } = useAttachmentIndexed(attachmentId);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [previewBase64, setPreviewBase64] = useState<string | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [previewFailed, setPreviewFailed] = useState(false);

  const remoteUri = useMemo(
    () => resolveAttachmentUri({ attachmentId, localUri, path }),
    [attachmentId, localUri, path],
  );

  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const canRenderInline = previewWebView?.mode === "rnc";
  const { canMount, onLoaded } = useDeferredWebViewMount(
    Boolean(remoteUri && canRenderInline && !compact),
  );

  useEffect(() => {
    setPreviewBase64(null);
    setPreviewFailed(false);
  }, [remoteUri]);

  useEffect(() => {
    if (!remoteUri || !canRenderInline || compact || !canMount) return;
    let cancelled = false;
    setLoadingPreview(true);
    void (async () => {
      try {
        const b64 = await fetchAttachmentBase64(remoteUri, token);
        if (!cancelled) setPreviewBase64(b64);
      } catch {
        if (!cancelled) {
          setPreviewFailed(true);
          onLoaded();
        }
      } finally {
        if (!cancelled) setLoadingPreview(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [remoteUri, canRenderInline, compact, token, canMount, onLoaded]);

  const previewHtml = useMemo(
    () => (previewBase64 ? buildPdfPreviewHtml(previewBase64, theme) : null),
    [previewBase64, theme],
  );
  const onShouldStartLoadWithRequest = useStaticOnlyNavigation(previewHtml);

  const handleShare = useCallback(async () => {
    if (!remoteUri) return;
    try {
      await downloadChatAttachment({ uri: remoteUri, token, fileName });
    } catch (error) {
      Alert.alert(
        t("common.download_failed"),
        error instanceof Error ? error.message : t("chat.pdf_export_failed"),
      );
    }
  }, [remoteUri, token, fileName, t]);

  if (!remoteUri) return null;

  return (
    <>
      <Pressable
        style={s.card}
        onPress={() => setViewerOpen(true)}
        accessibilityLabel={t("chat.pdf_open_a11y", { fileName })}
        accessibilityRole="button"
      >
        <View style={s.iconWrap}>
          <Icon name="document-text-outline" size={22} color={theme.primary} />
        </View>
        <View style={s.meta}>
          <Text style={s.name} numberOfLines={2}>
            {fileName}
          </Text>
          <Text style={s.kind}>
            {indexFailed ? t("chat.file_index_failed") : indexed ? "PDF" : t("chat.file_indexing")}
          </Text>
        </View>
        <Icon name="chevron-forward" size={18} color={theme.textTertiary} />
      </Pressable>

      {!compact && canRenderInline && WebView && canMount && previewHtml ? (
        <Pressable style={s.previewWrap} onPress={() => setViewerOpen(true)}>
          <WebView
            originWhitelist={STATIC_HTML_ORIGIN_WHITELIST}
            source={{ html: previewHtml }}
            scrollEnabled={false}
            style={s.previewWeb}
            javaScriptEnabled
            onLoadEnd={onLoaded}
            onShouldStartLoadWithRequest={onShouldStartLoadWithRequest}
          />
        </Pressable>
      ) : !compact && canRenderInline && (!canMount || loadingPreview) ? (
        <View style={s.previewWrap}>
          <ActivityIndicator color={theme.primary} />
        </View>
      ) : !compact && previewFailed ? (
        <Text style={s.fallbackHint}>{t("chat.pdf_preview_hint")}</Text>
      ) : null}

      <AttachmentPdfViewer
        visible={viewerOpen}
        onClose={() => setViewerOpen(false)}
        attachmentId={attachmentId}
        localUri={localUri}
        path={path}
        fileName={fileName}
        onShare={handleShare}
      />
    </>
  );
}

function makeStyles(t: Theme, compact: boolean) {
  return StyleSheet.create({
    card: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      paddingHorizontal: 12,
      paddingVertical: compact ? 8 : 10,
      borderRadius: 14,
      backgroundColor: t.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      maxWidth: compact ? "100%" : 280,
    },
    iconWrap: {
      width: 36,
      height: 36,
      borderRadius: 10,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: t.primaryLight,
    },
    meta: { flex: 1, minWidth: 0 },
    name: { fontSize: 14, fontWeight: "600", color: t.text },
    kind: { ...Type.meta, color: t.textTertiary, marginTop: 2 },
    previewWrap: {
      marginTop: 8,
      height: 180,
      borderRadius: 12,
      overflow: "hidden",
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      backgroundColor: t.bg,
      alignItems: "center",
      justifyContent: "center",
    },
    previewWeb: { flex: 1, width: "100%", backgroundColor: "transparent" },
    fallbackHint: { fontSize: 12, color: t.textTertiary, marginTop: 6 },
  });
}
