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

import { AttachmentPdfViewer } from "@/features/attachments/components/AttachmentPdfViewer";
import { Icon } from "@/ui/icons/Icon";

import { useAuthToken } from "@/contexts/AuthContext";
import { useAttachmentIndexed } from "@/features/attachments/hooks/useAttachmentIndexed";
import { useDeferredWebViewMount } from "@/hooks/useDeferredWebViewMount";
import { resolveAttachmentUri } from "@/features/attachments/model/attachmentUri";
import { downloadChatAttachment } from "@/features/attachments/model/downloadChatAttachment";
import { fetchAttachmentBase64 } from "@/features/attachments/model/fetchAttachmentBytes";
import { buildPdfPreviewHtml } from "@/lib/pdfPreviewHtml";
import { IconSize } from "@/ui/icons/sizes";
import { Theme, useTheme } from "@/lib/theme";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
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
          <Icon name="file-text" size={IconSize.md} color={theme.primary} />
        </View>
        <View style={s.meta}>
          <Text style={s.name} numberOfLines={2}>
            {fileName}
          </Text>
          <Text style={s.kind}>
            {indexFailed ? t("chat.file_index_failed") : indexed ? "PDF" : t("chat.file_indexing")}
          </Text>
        </View>
        <Icon name="chevron-right" size={IconSize.sm} color={theme.textTertiary} />
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
      paddingHorizontal: Space.sm,
      paddingVertical: compact ? 8 : 10,
      borderRadius: Radius.lg,
      backgroundColor: t.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      maxWidth: compact ? "100%" : 280,
    },
    iconWrap: {
      width: 36,
      height: 36,
      borderRadius: Radius.sm,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: t.primaryLight,
    },
    meta: { flex: 1, minWidth: 0 },
    name: { ...Type.label, color: t.text },
    kind: { ...Type.meta, color: t.textTertiary, marginTop: 2 },
    previewWrap: {
      marginTop: Space.xs,
      height: 180,
      borderRadius: Radius.md,
      overflow: "hidden",
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      backgroundColor: t.bg,
      alignItems: "center",
      justifyContent: "center",
    },
    previewWeb: { flex: 1, width: "100%", backgroundColor: "transparent" },
    fallbackHint: { ...Type.meta, color: t.textTertiary, marginTop: 6 },
  });
}
