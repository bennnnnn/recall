import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAuth } from "@/contexts/AuthContext";
import { resolveAttachmentUri } from "@/lib/attachmentUri";
import { downloadChatAttachment } from "@/lib/downloadChatAttachment";
import { fetchAttachmentBase64 } from "@/lib/fetchAttachmentBytes";
import { buildPdfPreviewHtml } from "@/lib/pdfPreviewHtml";
import { Theme, useTheme } from "@/lib/theme";
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
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme, compact), [theme, compact]);
  const { token } = useAuth();
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

  useEffect(() => {
    setPreviewBase64(null);
    setPreviewFailed(false);
  }, [remoteUri]);

  useEffect(() => {
    if (!remoteUri || !canRenderInline || compact) return;
    let cancelled = false;
    setLoadingPreview(true);
    void (async () => {
      try {
        const b64 = await fetchAttachmentBase64(remoteUri, token);
        if (!cancelled) setPreviewBase64(b64);
      } catch {
        if (!cancelled) setPreviewFailed(true);
      } finally {
        if (!cancelled) setLoadingPreview(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [remoteUri, canRenderInline, compact, token]);

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
        "Download failed",
        error instanceof Error ? error.message : "Could not export this PDF.",
      );
    }
  }, [remoteUri, token, fileName]);

  if (!remoteUri) return null;

  return (
    <>
      <Pressable
        style={s.card}
        onPress={() => setViewerOpen(true)}
        accessibilityLabel={`Open PDF ${fileName}`}
        accessibilityRole="button"
      >
        <View style={s.iconWrap}>
          <Ionicons name="document-text-outline" size={22} color={theme.primary} />
        </View>
        <View style={s.meta}>
          <Text style={s.name} numberOfLines={2}>
            {fileName}
          </Text>
          <Text style={s.kind}>PDF</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={theme.textTertiary} />
      </Pressable>

      {!compact && canRenderInline && WebView && previewHtml ? (
        <Pressable style={s.previewWrap} onPress={() => setViewerOpen(true)}>
          <WebView
            originWhitelist={STATIC_HTML_ORIGIN_WHITELIST}
            source={{ html: previewHtml }}
            scrollEnabled={false}
            style={s.previewWeb}
            javaScriptEnabled
            onShouldStartLoadWithRequest={onShouldStartLoadWithRequest}
          />
        </Pressable>
      ) : !compact && loadingPreview ? (
        <View style={s.previewWrap}>
          <ActivityIndicator color={theme.primary} />
        </View>
      ) : !compact && previewFailed ? (
        <Text style={s.fallbackHint}>Tap to open PDF preview.</Text>
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

type ViewerProps = {
  visible: boolean;
  onClose: () => void;
  attachmentId?: string | null;
  localUri?: string | null;
  path?: string | null;
  fileName: string;
  onShare: () => void;
};

function AttachmentPdfViewer({
  visible,
  onClose,
  attachmentId,
  localUri,
  path,
  fileName,
  onShare,
}: ViewerProps) {
  const theme = useTheme();
  const s = useMemo(() => makeViewerStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const { token } = useAuth();
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
          <Pressable onPress={onClose} hitSlop={8} accessibilityLabel="Close PDF">
            <Ionicons name="close" size={24} color={theme.text} />
          </Pressable>
          <Text style={s.title} numberOfLines={1}>
            {fileName}
          </Text>
          <Pressable onPress={onShare} hitSlop={8} accessibilityLabel="Share PDF">
            <Ionicons name="share-outline" size={22} color={theme.primary} />
          </Pressable>
        </View>
        <View style={s.body}>
          {loading ? (
            <ActivityIndicator color={theme.primary} size="large" />
          ) : failed || !WebView || !html ? (
            <Text style={s.error}>Could not preview this PDF.</Text>
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
    kind: { fontSize: 12, color: t.textTertiary, marginTop: 2 },
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
    title: { flex: 1, fontSize: 16, fontWeight: "600", color: t.text },
    body: { flex: 1, alignItems: "center", justifyContent: "center" },
    webview: { flex: 1, width: "100%", backgroundColor: t.bg },
    error: { color: t.textSecondary, fontSize: 15, paddingHorizontal: 24, textAlign: "center" },
  });
}
