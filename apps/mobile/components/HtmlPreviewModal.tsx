import {
  Component,
  useEffect,
  useMemo,
  useState,
  type ErrorInfo,
  type ReactNode,
} from "react";
import {
  ActivityIndicator,
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
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { CodeBlock } from "@/components/CodeBlock";
import { type IoniconName } from "@/lib/icons";
import { Theme, useTheme } from "@/lib/theme";
import { htmlForInlinePreview } from "@/lib/htmlForInlinePreview";
import {
  looksLikeInteractiveHtml,
  shareHtmlPreview,
  wrapFullDocument,
} from "@/lib/openHtmlPreview";
import {
  prepareHtmlRunDocument,
  stripScripts,
} from "@/lib/previewSandbox";
import { CODE_FONT } from "@/lib/fonts";
import { Space } from "@/lib/space";
import { Radius } from "@/lib/radius";
import { getPreviewWebView, HTML_RUN_ORIGIN_WHITELIST } from "@/lib/webView";

const EMPTY_CHECK_SCRIPT =
  "<script>(function(){function chk(){var b=document.body;if(!b)return;var txt=(b.innerText||'').trim();var imgs=b.querySelectorAll('img,svg,canvas,video,iframe').length;var els=b.querySelectorAll('div,section,main,article,p,span,ul,ol,table,pre,code,h1,h2,h3,h4,h5,h6').length;if(!txt&&!imgs&&els<=1){try{window.ReactNativeWebView&&window.ReactNativeWebView.postMessage(JSON.stringify({kind:'preview-empty'}));}catch(e){}}}if(document.readyState==='complete'){chk();}else{window.addEventListener('load',function(){setTimeout(chk,300);});}})();</script>";

class PreviewRenderBoundary extends Component<
  {
    children: ReactNode;
    resetKey: string;
    errorColor: string;
    errorMessage: string;
  },
  { hasError: boolean }
> {
  state: { hasError: boolean } = { hasError: false };

  static getDerivedStateFromError(): { hasError: boolean } {
    return { hasError: true };
  }

  componentDidUpdate(prevProps: { resetKey: string }): void {
    if (prevProps.resetKey !== this.props.resetKey && this.state.hasError) {
      this.setState({ hasError: false });
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.warn("HtmlPreviewModal render failed", error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <View style={{ padding: 16 }}>
          <Text
            style={{
              color: this.props.errorColor,
              fontSize: 14,
              lineHeight: 20,
            }}
          >
            {this.props.errorMessage}
          </Text>
        </View>
      );
    }
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
 * Sandboxed HTML Run tab (RNC WebView only).
 *
 * Keep this path as close as charts: `source={{ html }}`, no baseUrl, no
 * onShouldStartLoadWithRequest. CDN is allowed by PREVIEW_CSP_LIVE; leave-page
 * is blocked by an in-document script (click/submit/location/open), stripping
 * meta-refresh, form-action 'none', and `domStorageEnabled={false}`.
 */
function LiveWebPreview({
  html,
  theme,
  styles: s,
}: {
  html: string;
  theme: Theme;
  styles: ReturnType<typeof makeStyles>;
}) {
  const { t } = useTranslation();
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [empty, setEmpty] = useState(false);
  const previewWebView = useMemo(() => getPreviewWebView(), []);

  const fullHtml = useMemo(
    () => prepareHtmlRunDocument(wrapFullDocument(html, theme)) + EMPTY_CHECK_SCRIPT,
    [html, theme],
  );
  const source = useMemo(() => ({ html: fullHtml }), [fullHtml]);

  useEffect(() => {
    setLoadError(null);
    setLoading(true);
    setEmpty(false);
  }, [html]);

  const WebView = previewWebView?.mode === "rnc" ? previewWebView.Component : null;
  if (!WebView) {
    return (
      <View style={s.scrollContent}>
        <Text style={s.base}>{t("preview.webview_unavailable")}</Text>
      </View>
    );
  }

  return (
    <View style={s.webviewContainer} collapsable={false}>
      {loadError ? (
        <View style={s.emptyOverlay} pointerEvents="none">
          <Text style={s.emptyOverlayText}>{loadError}</Text>
        </View>
      ) : empty ? (
        <View style={s.emptyOverlay} pointerEvents="none">
          <Text style={s.emptyOverlayText}>{t("preview.empty_sandbox")}</Text>
        </View>
      ) : loading ? (
        <View style={s.emptyOverlay} pointerEvents="none">
          <ActivityIndicator color={theme.primary} />
          <Text style={[s.emptyOverlayText, { marginTop: 8 }]}>
            {t("preview.loading")}
          </Text>
        </View>
      ) : null}
      <WebView
        source={source}
        style={s.webview}
        scrollEnabled
        originWhitelist={HTML_RUN_ORIGIN_WHITELIST}
        javaScriptEnabled
        domStorageEnabled={false}
        allowsInlineMediaPlayback
        mixedContentMode="always"
        setSupportMultipleWindows={false}
        nestedScrollEnabled
        onLoadStart={() => setLoading(true)}
        onLoadEnd={() => setLoading(false)}
        onMessage={(e: { nativeEvent?: { data?: string } }) => {
          try {
            const data = JSON.parse(e.nativeEvent?.data ?? "{}");
            if (data && data.kind === "preview-empty") setEmpty(true);
          } catch {
            /* ignore non-JSON messages */
          }
        }}
        onError={(e: { nativeEvent?: { description?: string } }) => {
          const detail = e.nativeEvent?.description?.trim();
          setLoadError(detail || t("preview.load_error"));
        }}
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
  const previewHtml = useMemo(
    () => htmlForInlinePreview(stripScripts(html)),
    [html],
  );
  const tagStyles = useMemo(() => makeTagStyles(theme), [theme]);

  return (
    <ScrollView
      style={s.scroll}
      contentContainerStyle={s.scrollContent}
      showsVerticalScrollIndicator
    >
      <RenderHtml
        contentWidth={contentWidth}
        source={{ html: previewHtml }}
        baseStyle={s.base}
        tagsStyles={tagStyles}
      />
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
  icon: IoniconName;
  label: string;
  onPress: () => void;
  active?: boolean;
  theme: Theme;
  styles: ReturnType<typeof makeStyles>;
}) {
  const color = active ? theme.primary : theme.textSecondary;
  return (
    <Pressable
      style={[s.toolbarItem, active && s.toolbarItemActive]}
      onPress={onPress}
      hitSlop={8}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected: active }}
    >
      <Icon name={icon} size={24} color={color} />
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
  // Bare RNC only — do not treat expo-dom as a live Run path (file:// blanks).
  const canUseNativeWebView = useMemo(
    () => getPreviewWebView()?.mode === "rnc",
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
            <Icon name="flash-outline" size={16} color={theme.primary} />
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
          ) : canUseNativeWebView ? (
            <PreviewRenderBoundary
              resetKey={html}
              errorColor={theme.danger}
              errorMessage={t("preview.render_failed")}
            >
              <LiveWebPreview html={html} theme={theme} styles={s} />
            </PreviewRenderBoundary>
          ) : (
            <StaticHtmlPreview
              html={html}
              contentWidth={contentWidth}
              theme={theme}
              styles={s}
            />
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
      gap: Space.xs,
      marginHorizontal: Space.md,
      marginTop: 10,
      paddingHorizontal: Space.sm,
      paddingVertical: 10,
      borderRadius: Radius.sm,
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
    codeScrollContent: { padding: Space.md, paddingBottom: Space.lg },
    webviewContainer: {
      flex: 1,
      alignSelf: "stretch",
      position: "relative",
      minHeight: 200,
      backgroundColor: theme.bg,
    },
    // Absolute fill — never gate mount on onLayout height (Modal blank bug).
    webview: {
      position: "absolute",
      top: 0,
      right: 0,
      bottom: 0,
      left: 0,
      backgroundColor: theme.bg,
    },
    emptyOverlay: {
      position: "absolute",
      zIndex: 2,
      top: Space.md,
      left: Space.md,
      right: Space.md,
      padding: 14,
      borderRadius: Radius.sm,
      backgroundColor: theme.surfaceAlt,
    },
    emptyOverlayText: {
      fontSize: 14,
      lineHeight: 20,
      color: theme.text,
    },
    scroll: { flex: 1 },
    scrollContent: { paddingHorizontal: Space.md, paddingVertical: Space.md, paddingBottom: Space.md },
    base: { color: theme.text, fontSize: 16, lineHeight: 22 },
    toolbar: {
      flexDirection: "row",
      alignItems: "stretch",
      justifyContent: "space-around",
      paddingHorizontal: Space.xs,
      paddingTop: Space.xs,
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
      borderRadius: Radius.sm,
    },
    toolbarItemActive: {
      backgroundColor: theme.primaryLight,
    },
  });
