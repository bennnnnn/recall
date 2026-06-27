import { useEffect, useMemo, useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import RenderHtml from "react-native-render-html";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { C } from "@/constants/Colors";
import {
  htmlForInlinePreview,
  previewHasVisibleText,
} from "@/lib/htmlForInlinePreview";
import {
  looksLikeInteractiveHtml,
  openHtmlInBrowser,
  wrapFullDocument,
  writeHtmlPreviewFile,
} from "@/lib/openHtmlPreview";
import { CODE_FONT } from "@/lib/fonts";
import { getPreviewWebView } from "@/lib/webView";

type Props = {
  visible: boolean;
  html: string;
  title?: string;
  onClose: () => void;
};

const TAG_STYLES = {
  body: { color: C.text },
  p: { marginTop: 0, marginBottom: 10, lineHeight: 22 },
  h1: { fontSize: 28, fontWeight: "700" as const, marginBottom: 12, color: C.text },
  h2: { fontSize: 22, fontWeight: "700" as const, marginBottom: 10, color: C.text },
  h3: { fontSize: 18, fontWeight: "700" as const, marginBottom: 8, color: C.text },
  a: { color: C.primary },
  div: { color: C.text },
  span: { color: C.text },
  table: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
    marginVertical: 8,
  },
  th: {
    backgroundColor: C.surface,
    padding: 8,
    fontWeight: "700" as const,
  },
  td: { padding: 8 },
  pre: {
    backgroundColor: C.codeBg,
    padding: 12,
    borderRadius: 8,
    fontFamily: CODE_FONT,
    fontSize: 12,
    lineHeight: 18,
  },
  code: { fontFamily: CODE_FONT, fontSize: 14 },
  img: { marginVertical: 8 },
};

function LiveWebPreview({ html }: { html: string }) {
  const fullHtml = useMemo(() => wrapFullDocument(html), [html]);
  const previewWebView = useMemo(() => getPreviewWebView(), []);
  const [previewUri, setPreviewUri] = useState<string | null>(null);

  useEffect(() => {
    if (previewWebView?.mode !== "expo-dom") {
      setPreviewUri(null);
      return;
    }
    // @expo/dom-webview only supports { uri } in source (no inline html).
    // data: URIs are not resolved by Image.resolveAssetSource, so always
    // write to a cache file to get a real file:// URI.
    let cancelled = false;
    void writeHtmlPreviewFile(fullHtml).then((uri) => {
      if (!cancelled) setPreviewUri(uri);
    });
    return () => {
      cancelled = true;
    };
  }, [fullHtml, previewWebView?.mode]);

  const WebView = previewWebView?.Component;
  if (!WebView) return null;

  const isRnc = previewWebView.mode === "rnc";
  const source = isRnc
    ? { html: fullHtml, baseUrl: "https://localhost/" }
    : previewUri
      ? { uri: previewUri }
      : null;

  if (!source) {
    return (
      <View style={s.loading}>
        <Text style={s.loadingText}>Loading preview…</Text>
      </View>
    );
  }

  return (
    <View style={s.webviewContainer}>
      <WebView
        source={source}
        style={s.webview}
        scrollEnabled
        {...(isRnc
          ? {
              originWhitelist: ["*"],
              javaScriptEnabled: true,
              domStorageEnabled: true,
              allowsInlineMediaPlayback: true,
            }
          : { allowsInlineMediaPlayback: true, containerStyle: s.webviewContainer })}
      />
    </View>
  );
}

function StaticHtmlPreview({ html, contentWidth }: { html: string; contentWidth: number }) {
  const previewHtml = useMemo(() => htmlForInlinePreview(html), [html]);
  const showRenderHtml = previewHasVisibleText(html);

  return (
    <ScrollView
      style={s.scroll}
      contentContainerStyle={s.scrollContent}
      showsVerticalScrollIndicator
    >
      {showRenderHtml ? (
        <RenderHtml
          contentWidth={contentWidth}
          source={{ html: previewHtml }}
          baseStyle={s.base}
          tagsStyles={TAG_STYLES}
        />
      ) : (
        <Text style={s.sourceText} selectable>
          {html.trim()}
        </Text>
      )}
    </ScrollView>
  );
}

export function HtmlPreviewModal({
  visible,
  html,
  title = "Preview",
  onClose,
}: Props) {
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const contentWidth = Math.max(width - 32, 280);
  const interactive = useMemo(() => looksLikeInteractiveHtml(html), [html]);
  const canUseWebView = useMemo(() => getPreviewWebView() != null, []);

  const openBrowser = () => {
    void openHtmlInBrowser(html);
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="fullScreen"
      onRequestClose={onClose}
    >
      <View
        style={[s.root, { paddingTop: insets.top, paddingBottom: insets.bottom }]}
      >
        <View style={s.header}>
          <Text style={s.title} numberOfLines={1}>
            {title}
          </Text>
          <View style={s.headerActions}>
            <Pressable style={s.iconBtn} onPress={openBrowser} hitSlop={8}>
              <Ionicons name="open-outline" size={22} color={C.text} />
            </Pressable>
            <Pressable style={s.iconBtn} onPress={onClose} hitSlop={8}>
              <Ionicons name="close" size={26} color={C.text} />
            </Pressable>
          </View>
        </View>

        {interactive || !canUseWebView ? (
          <Pressable style={s.interactiveBanner} onPress={openBrowser}>
            <Ionicons
              name={interactive ? "flash-outline" : "globe-outline"}
              size={16}
              color={C.primary}
            />
            <Text style={s.interactiveBannerText}>
              {interactive
                ? "This page uses JavaScript — tap here or ↗ to open the live version in Safari"
                : "Tap here or ↗ to open the full page in Safari"}
            </Text>
          </Pressable>
        ) : null}

        <View style={s.body}>
          {canUseWebView ? (
            <LiveWebPreview html={html} />
          ) : (
            <StaticHtmlPreview html={html} contentWidth={contentWidth} />
          )}
        </View>

        <View style={s.footer}>
          <Pressable
            style={s.footerIconBtn}
            onPress={openBrowser}
            hitSlop={8}
            accessibilityLabel="Open in Safari"
          >
            <Ionicons name="open-outline" size={22} color={C.primary} />
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
  },
  title: {
    flex: 1,
    fontSize: 17,
    fontWeight: "700",
    color: C.text,
    marginRight: 8,
  },
  headerActions: { flexDirection: "row", alignItems: "center", gap: 4 },
  iconBtn: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 10,
  },
  interactiveBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginHorizontal: 16,
    marginTop: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: C.primaryLight,
  },
  interactiveBannerText: {
    flex: 1,
    fontSize: 13,
    lineHeight: 18,
    color: C.text,
  },
  body: { flex: 1, minHeight: 0 },
  webviewContainer: { flex: 1, alignSelf: "stretch" },
  webview: { flex: 1, backgroundColor: "#fff" },
  loading: { flex: 1, alignItems: "center", justifyContent: "center" },
  loadingText: { fontSize: 15, color: C.textSecondary },
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 16, paddingVertical: 16, paddingBottom: 16 },
  base: { color: C.text, fontSize: 16, lineHeight: 22 },
  sourceText: {
    fontFamily: CODE_FONT,
    fontSize: 12,
    lineHeight: 18,
    color: C.text,
  },
  footer: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: C.border,
    backgroundColor: C.bg,
  },
  footerIconBtn: {
    width: 48,
    height: 48,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
    backgroundColor: C.primaryLight,
  },
});
