import { Component, useEffect, useMemo, useState, type ErrorInfo, type ReactNode } from "react";
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
import { useTranslation } from "react-i18next";

import { CodeBlock } from "@/components/CodeBlock";
import { Theme, useTheme } from "@/lib/theme";
import {
  htmlForInlinePreview,
  previewHasVisibleText,
} from "@/lib/htmlForInlinePreview";
import {
  looksLikeInteractiveHtml,
  shareHtmlPreview,
  wrapFullDocument,
} from "@/lib/openHtmlPreview";
import { injectPreviewCsp, stripScripts } from "@/lib/previewSandbox";
import { CODE_FONT } from "@/lib/fonts";
import Constants, { ExecutionEnvironment } from "expo-constants";
import { getPreviewWebView, useStaticOnlyNavigation } from "@/lib/webView";

class PreviewRenderBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.warn("HtmlPreviewModal render failed", error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.failed) return this.props.fallback;
    return this.props.children;
  }
}

type Props = {
  visible: boolean;
  html: string;
  onClose: () => void;
};

type PreviewTab = "run" | "code";

function makeTagStyles(theme: Theme) {
  return {
    body: { color: theme.text },
    p: { marginTop: 0, marginBottom: 10, lineHeight: 22 },
    h1: { fontSize: 28, fontWeight: "700" as const, marginBottom: 12, color: theme.text },
    h2: { fontSize: 22, fontWeight: "700" as const, marginBottom: 10, color: theme.text },
    h3: { fontSize: 18, fontWeight: "700" as const, marginBottom: 8, color: theme.text },
    a: { color: theme.primary },
    div: { color: theme.text },
    span: { color: theme.text },
    table: {
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      marginVertical: 8,
    },
    th: {
      backgroundColor: theme.surface,
      padding: 8,
      fontWeight: "700" as const,
    },
    td: { padding: 8 },
    pre: {
      backgroundColor: theme.codeBg,
      padding: 12,
      borderRadius: 8,
      fontFamily: CODE_FONT,
      fontSize: 12,
      lineHeight: 18,
    },
    code: { fontFamily: CODE_FONT, fontSize: 14 },
    img: { marginVertical: 8 },
  };
}

/**
 * Native react-native-webview path (dev build). Expo Go's `@expo/dom-webview`
 * file:// path often paints a blank view — callers should use StaticHtmlPreview
 * there instead.
 */
function LiveWebPreview({
  html,
  styles: s,
}: {
  html: string;
  styles: ReturnType<typeof makeStyles>;
}) {
  // Drop CSP `sandbox` in meta — some WKWebView builds treat it harshly and
  // paint an empty document; connect-src/script-src still lock down egress.
  const fullHtml = useMemo(
    () =>
      injectPreviewCsp(wrapFullDocument(html)).replace(
        /sandbox allow-scripts;?\s*/gi,
        "",
      ),
    [html],
  );
  const previewWebView = useMemo(() => getPreviewWebView(), []);
  const onShouldStartLoadWithRequest = useStaticOnlyNavigation(fullHtml);

  const WebView = previewWebView?.mode === "rnc" ? previewWebView.Component : null;
  if (!WebView) return null;

  return (
    <View style={s.webviewContainer}>
      <WebView
        source={{ html: fullHtml, baseUrl: "about:blank" }}
        style={s.webview}
        scrollEnabled
        onShouldStartLoadWithRequest={onShouldStartLoadWithRequest}
        // Guard blocks http(s); wildcard lets the inline document load. Tight
        // about:blank-only whitelist left this view blank on some iOS builds.
        originWhitelist={["*", "about:blank"]}
        javaScriptEnabled
        domStorageEnabled={false}
        allowsInlineMediaPlayback
        setSupportMultipleWindows={false}
      />
    </View>
  );
}

function StaticHtmlPreview({
  html,
  contentWidth,
  theme,
  styles: s,
}: {
  html: string;
  contentWidth: number;
  theme: Theme;
  styles: ReturnType<typeof makeStyles>;
}) {
  // Expo Go static fallback path: react-native-render-html doesn't execute
  // <script>, but stripScripts also removes javascript:/vbscript: URLs, inline
  // event handlers, srcdoc iframes, and meta-refresh — so a model-emitted
  // payload that would be a zero-click vector in a browser is inert even in
  // the static view, and the source-text fallback doesn't dump raw <script>
  // bodies as visible text.
  const previewHtml = useMemo(
    () => htmlForInlinePreview(stripScripts(html)),
    [html],
  );
  const showRenderHtml = previewHasVisibleText(html);
  const tagStyles = useMemo(() => makeTagStyles(theme), [theme]);

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
          tagsStyles={tagStyles}
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
  theme,
  styles: s,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  onPress: () => void;
  active?: boolean;
  theme: Theme;
  styles: ReturnType<typeof makeStyles>;
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
        color={active ? theme.primary : theme.textSecondary}
      />
    </Pressable>
  );
}

export function HtmlPreviewModal({ visible, html, onClose }: Props) {
  const insets = useSafeAreaInsets();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { width } = useWindowDimensions();
  const contentWidth = Math.max(width - 32, 280);
  const [tab, setTab] = useState<PreviewTab>("run");
  const interactive = useMemo(() => looksLikeInteractiveHtml(html), [html]);
  // Live WebView only in a bare/dev-client native binary. Expo Go
  // (`storeClient`) and store builds without RNC stay on static HTML — the
  // WebView path was painting a blank Run tab for this user.
  const canUseNativeWebView = useMemo(
    () =>
      Constants.executionEnvironment === ExecutionEnvironment.Bare &&
      getPreviewWebView()?.mode === "rnc",
    [],
  );

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
        {tab === "run" && interactive && !canUseNativeWebView ? (
          <View style={s.interactiveBanner}>
            <Ionicons name="flash-outline" size={16} color={theme.primary} />
            <Text style={s.interactiveBannerText}>{t("preview.expo_go_banner")}</Text>
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
          ) : (
            <PreviewRenderBoundary
              fallback={
                <ScrollView
                  style={s.scroll}
                  contentContainerStyle={s.scrollContent}
                >
                  <Text style={s.base}>
                    {t("preview.expo_go_banner")}
                  </Text>
                  <Text style={s.sourceText} selectable>
                    {html.trim().slice(0, 4000)}
                  </Text>
                </ScrollView>
              }
            >
              {canUseNativeWebView ? (
                <LiveWebPreview html={html} styles={s} />
              ) : (
                <StaticHtmlPreview
                  html={html}
                  contentWidth={contentWidth}
                  theme={theme}
                  styles={s}
                />
              )}
            </PreviewRenderBoundary>
          )}
        </View>

        <View style={s.toolbar}>
          <ToolbarItem
            icon="close"
            label={t("preview.close")}
            onPress={onClose}
            theme={theme}
            styles={s}
          />
          <ToolbarItem
            icon="code-slash"
            label={t("preview.code_tab")}
            onPress={() => setTab("code")}
            active={tab === "code"}
            theme={theme}
            styles={s}
          />
          <ToolbarItem
            icon="play"
            label={t("preview.run_tab")}
            onPress={() => setTab("run")}
            active={tab === "run"}
            theme={theme}
            styles={s}
          />
          <ToolbarItem
            icon="share-outline"
            label={t("preview.share")}
            onPress={() => void shareHtmlPreview(html)}
            theme={theme}
            styles={s}
          />
        </View>
      </View>
    </Modal>
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.bg },
  interactiveBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginHorizontal: 16,
    marginTop: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: theme.primaryLight,
  },
  interactiveBannerText: {
    flex: 1,
    fontSize: 13,
    lineHeight: 18,
    color: theme.text,
  },
  body: { flex: 1, minHeight: 0 },
  codeScroll: { flex: 1 },
  codeScrollContent: { padding: 16, paddingBottom: 24 },
  webviewContainer: { flex: 1, alignSelf: "stretch" },
  webview: { flex: 1, backgroundColor: theme.surface },
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 16, paddingVertical: 16, paddingBottom: 16 },
  base: { color: theme.text, fontSize: 16, lineHeight: 22 },
  sourceText: {
    fontFamily: CODE_FONT,
    fontSize: 12,
    lineHeight: 18,
    color: theme.text,
  },
  toolbar: {
    flexDirection: "row",
    alignItems: "stretch",
    justifyContent: "space-around",
    paddingHorizontal: 8,
    paddingTop: 8,
    paddingBottom: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: theme.border,
    backgroundColor: theme.bg,
  },
  toolbarItem: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 10,
    borderRadius: 10,
  },
  toolbarItemActive: {
    backgroundColor: theme.primaryLight,
  },
});
