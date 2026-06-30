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

import { CodeBlock } from "@/components/CodeBlock";
import { C } from "@/constants/Colors";
import {
  htmlForInlinePreview,
  previewHasVisibleText,
} from "@/lib/htmlForInlinePreview";
import {
  looksLikeInteractiveHtml,
  shareHtmlPreview,
  wrapFullDocument,
  writeHtmlPreviewFile,
} from "@/lib/openHtmlPreview";
import { injectPreviewCsp } from "@/lib/previewSandbox";
import { CODE_FONT } from "@/lib/fonts";
import { getPreviewWebView } from "@/lib/webView";

type Props = {
  visible: boolean;
  html: string;
  onClose: () => void;
};

type PreviewTab = "run" | "code";

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
  const fullHtml = useMemo(() => injectPreviewCsp(wrapFullDocument(html)), [html]);
  const previewWebView = useMemo(() => getPreviewWebView(), []);
  const [previewUri, setPreviewUri] = useState<string | null>(null);

  useEffect(() => {
    if (previewWebView?.mode !== "expo-dom") {
      setPreviewUri(null);
      return;
    }
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

function ToolbarItem({
  icon,
  label,
  onPress,
  active,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  onPress: () => void;
  active?: boolean;
}) {
  return (
    <Pressable
      style={[s.toolbarItem, active && s.toolbarItemActive]}
      onPress={onPress}
      hitSlop={8}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected: active }}
    >
      <Ionicons
        name={icon}
        size={24}
        color={active ? C.primary : C.textSecondary}
      />
    </Pressable>
  );
}

export function HtmlPreviewModal({ visible, html, onClose }: Props) {
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const contentWidth = Math.max(width - 32, 280);
  const [tab, setTab] = useState<PreviewTab>("run");
  const interactive = useMemo(() => looksLikeInteractiveHtml(html), [html]);
  const canUseWebView = useMemo(() => getPreviewWebView() != null, []);

  useEffect(() => {
    if (visible) setTab("run");
  }, [visible]);

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
        {tab === "run" && interactive && !canUseWebView ? (
          <View style={s.interactiveBanner}>
            <Ionicons name="flash-outline" size={16} color={C.primary} />
            <Text style={s.interactiveBannerText}>
              This page uses JavaScript — switch to Run with a dev build for live
              preview, or Share to open in Safari.
            </Text>
          </View>
        ) : null}

        <View style={s.body}>
          {tab === "code" ? (
            <ScrollView
              style={s.codeScroll}
              contentContainerStyle={s.codeScrollContent}
              showsVerticalScrollIndicator
            >
              <CodeBlock code={html} lang="html" />
            </ScrollView>
          ) : canUseWebView ? (
            <LiveWebPreview html={html} />
          ) : (
            <StaticHtmlPreview html={html} contentWidth={contentWidth} />
          )}
        </View>

        <View style={s.toolbar}>
          <ToolbarItem icon="close" label="Close" onPress={onClose} />
          <ToolbarItem
            icon="code-slash"
            label="Code"
            onPress={() => setTab("code")}
            active={tab === "code"}
          />
          <ToolbarItem
            icon="play"
            label="Run"
            onPress={() => setTab("run")}
            active={tab === "run"}
          />
          <ToolbarItem
            icon="share-outline"
            label="Share"
            onPress={() => void shareHtmlPreview(html)}
          />
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
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
  codeScroll: { flex: 1 },
  codeScrollContent: { padding: 16, paddingBottom: 24 },
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
  toolbar: {
    flexDirection: "row",
    alignItems: "stretch",
    justifyContent: "space-around",
    paddingHorizontal: 8,
    paddingTop: 8,
    paddingBottom: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: C.border,
    backgroundColor: C.bg,
  },
  toolbarItem: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 10,
    borderRadius: 10,
  },
  toolbarItemActive: {
    backgroundColor: C.primaryLight,
  },
});
