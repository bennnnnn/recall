/**
 * Mermaid diagram — inline SVG render via WebView (dev build), with source fallback.
 */
import { useCallback, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import * as WebBrowser from "expo-web-browser";
import { Icon } from "@/components/Icon";

import { CopyButton } from "@/components/CopyButton";
import { VisualCard } from "@/components/rich/VisualCard";
import { useDeferredWebViewMount } from "@/hooks/useDeferredWebViewMount";
import { CODE_FONT } from "@/lib/fonts";
import {
  MERMAID_HEIGHT_EPSILON_PX,
  MERMAID_MAX_EXPANDED,
  MERMAID_MAX_HEIGHT,
  MERMAID_MIN_HEIGHT,
  nextMermaidPreviewHeight,
} from "@/lib/mermaidPreviewHeight";
import { injectPreviewCsp, inlineScript } from "@/lib/previewSandbox";
import { Theme, useTheme } from "@/lib/theme";
import {
  getPreviewWebView,
  STATIC_HTML_ORIGIN_WHITELIST,
  useStaticOnlyNavigation,
} from "@/lib/webView";
import { MERMAID_MIN_JS } from "@/lib/vendor/mermaidMinJs";

type Props = { content: string };

type MermaidErrorMessage = { kind: "mermaid-error"; message?: string };
type MermaidSizeMessage = { kind: "mermaid-size"; height?: number };

function isMermaidErrorMessage(data: unknown): data is MermaidErrorMessage {
  return typeof data === "object" && data !== null && (data as { kind?: string }).kind === "mermaid-error";
}

function isMermaidSizeMessage(data: unknown): data is MermaidSizeMessage {
  return typeof data === "object" && data !== null && (data as { kind?: string }).kind === "mermaid-size";
}

function buildMermaidHtml(source: string, theme: Theme): string {
  const safeSpec = source
    .trim()
    .replace(/\\/g, "\\\\")
    .replace(/`/g, "\\`")
    .replace(/\$/g, "\\$")
    .replace(/<\/script>/gi, "<\\/script>");
  const mermaidTheme = theme.isDark ? "dark" : "neutral";
  return injectPreviewCsp(`<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script>${inlineScript(MERMAID_MIN_JS)}</script>
<style>
  body { margin: 0; padding: 8px; font-family: -apple-system, sans-serif; background: ${theme.bg}; }
  #err { color: ${theme.danger}; font-size: 12px; display: none; white-space: pre-wrap; padding: 8px; }
  .mermaid { display: flex; justify-content: center; }
</style>
</head>
<body>
<pre class="mermaid" id="diagram"></pre>
<div id="err"></div>
<script>
  const src = \`${safeSpec}\`;
  function reportError(msg) {
    try { window.ReactNativeWebView && window.ReactNativeWebView.postMessage(JSON.stringify({ kind: 'mermaid-error', message: msg })); } catch (e) {}
    var el = document.getElementById('err');
    el.textContent = 'Diagram error: ' + msg;
    el.style.display = 'block';
  }
  function reportSize() {
    var svg = document.querySelector('#diagram svg');
    var h = 0;
    if (svg) {
      var box = svg.getBoundingClientRect();
      h = box.height;
    }
    if (!h) h = document.body.scrollHeight;
    try { window.ReactNativeWebView && window.ReactNativeWebView.postMessage(JSON.stringify({ kind: 'mermaid-size', height: Math.ceil(h + 16) })); } catch (e) {}
  }
  const el = document.getElementById('diagram');
  el.textContent = src;
  mermaid.initialize({
    startOnLoad: false,
    theme: '${mermaidTheme}',
    securityLevel: 'strict',
    flowchart: { useMaxWidth: true, htmlLabels: false },
  });
  mermaid.run({ nodes: [el] }).then(function() {
    requestAnimationFrame(reportSize);
  }).catch(function(err) { reportError(err && err.message ? err.message : String(err)); });
</script>
</body>
</html>`);
}

export function MermaidBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [showSource, setShowSource] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [previewHeight, setPreviewHeight] = useState(MERMAID_MIN_HEIGHT);
  const [reportedHeight, setReportedHeight] = useState(0);
  const heightRef = useRef(MERMAID_MIN_HEIGHT);
  const expandedRef = useRef(expanded);
  expandedRef.current = expanded;

  const mermaidHtml = useMemo(() => buildMermaidHtml(content.trim(), theme), [content, theme]);
  const source = useMemo(() => ({ html: mermaidHtml }), [mermaidHtml]);
  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const canRenderInline = previewWebView?.mode === "rnc";
  const { canMount, onLoaded } = useDeferredWebViewMount(Boolean(WebView) && canRenderInline);
  const onShouldStartLoadWithRequest = useStaticOnlyNavigation(mermaidHtml);

  const maxHeight = expanded ? MERMAID_MAX_EXPANDED : MERMAID_MAX_HEIGHT;
  const height = Math.min(previewHeight, maxHeight);
  const clipped = reportedHeight > height + MERMAID_HEIGHT_EPSILON_PX;

  const handleWebViewMessage = useCallback((event: { nativeEvent: { data?: string } }) => {
    try {
      const data: unknown = JSON.parse(event.nativeEvent.data ?? "{}");
      if (isMermaidErrorMessage(data)) {
        setRenderError(data.message ?? t("rich.mermaid_error"));
        return;
      }
      if (isMermaidSizeMessage(data)) {
        const reported = Number(data.height);
        if (!Number.isFinite(reported) || reported <= 0) return;
        setReportedHeight(reported);
        const maxH = expandedRef.current ? MERMAID_MAX_EXPANDED : MERMAID_MAX_HEIGHT;
        const next = nextMermaidPreviewHeight(reported, heightRef.current, maxH);
        if (next == null) return;
        heightRef.current = next;
        setPreviewHeight(next);
      }
    } catch {
      setRenderError(t("rich.mermaid_error"));
    }
  }, [t]);

  const handleOpenLiveEditor = useCallback(async () => {
    await Clipboard.setStringAsync(content);
    await WebBrowser.openBrowserAsync("https://mermaid.live/edit");
  }, [content]);

  const toggleExpanded = useCallback(() => {
    setExpanded((was) => {
      const next = !was;
      const maxH = next ? MERMAID_MAX_EXPANDED : MERMAID_MAX_HEIGHT;
      const reported = reportedHeight || heightRef.current;
      const clamped = Math.min(maxH, Math.max(MERMAID_MIN_HEIGHT, Math.ceil(reported)));
      heightRef.current = clamped;
      setPreviewHeight(clamped);
      return next;
    });
  }, [reportedHeight]);

  return (
    <VisualCard
      label={t("rich.mermaid_diagram")}
      icon="git-network-outline"
      headerRight={
        <Pressable
          onPress={() => setShowSource((v) => !v)}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel={showSource ? t("rich.diagram") : t("rich.source")}
        >
          <Icon
            name={showSource ? "eye-off-outline" : "code-slash-outline"}
            size={20}
            color={theme.primary}
          />
        </Pressable>
      }
      actions={
        <>
          <CopyButton text={content} />
          {clipped || expanded ? (
            <Pressable
              style={s.iconBtn}
              onPress={toggleExpanded}
              hitSlop={8}
              accessibilityRole="button"
              accessibilityLabel={expanded ? t("rich.collapse") : t("rich.expand")}
            >
              <Icon
                name={expanded ? "contract-outline" : "expand-outline"}
                size={20}
                color={theme.textSecondary}
              />
            </Pressable>
          ) : null}
          <Pressable style={s.openBtn} onPress={handleOpenLiveEditor} hitSlop={8}>
            <Icon name="open-outline" size={18} color={theme.onPrimary} />
            <Text style={s.openLabel}>{t("rich.mermaid_live")}</Text>
          </Pressable>
        </>
      }
    >
      {renderError ? (
        <View style={s.previewBox}>
          <Icon name="alert-circle-outline" size={20} color={theme.danger} />
          <Text style={[s.previewText, { color: theme.danger }]}>
            {renderError}
          </Text>
        </View>
      ) : showSource ? (
        <View style={s.previewBox}>
          <Text style={s.previewText}>{content.trim()}</Text>
        </View>
      ) : canRenderInline && WebView ? (
        canMount ? (
          <View style={[s.webWrap, { height }]}>
            <WebView
              originWhitelist={STATIC_HTML_ORIGIN_WHITELIST}
              source={source}
              scrollEnabled={clipped}
              nestedScrollEnabled={clipped}
              showsVerticalScrollIndicator={clipped}
              bounces={false}
              overScrollMode="never"
              style={s.webview}
              javaScriptEnabled
              domStorageEnabled={false}
              onLoadEnd={onLoaded}
              onMessage={handleWebViewMessage}
              onShouldStartLoadWithRequest={onShouldStartLoadWithRequest}
            />
          </View>
        ) : (
          <View style={s.loadingWrap}>
            <ActivityIndicator color={theme.primary} />
          </View>
        )
      ) : (
        <View style={s.previewBox}>
          <Text style={s.previewText} numberOfLines={6}>
            {content.trim()}
          </Text>
          <Text style={s.fallbackHint}>{t("rich.mermaid_dev_build")}</Text>
        </View>
      )}
    </VisualCard>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    webWrap: { backgroundColor: t.bg },
    webview: { flex: 1, backgroundColor: "transparent" },
    loadingWrap: {
      height: MERMAID_MIN_HEIGHT,
      backgroundColor: t.bg,
      alignItems: "center",
      justifyContent: "center",
    },
    previewBox: {
      paddingHorizontal: 14,
      paddingVertical: 10,
      backgroundColor: t.contentSurface,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
    },
    previewText: { fontFamily: CODE_FONT, fontSize: 11, lineHeight: 17, color: t.textSecondary },
    fallbackHint: { fontSize: 12, color: t.textTertiary, marginTop: 8 },
    iconBtn: {
      width: 32,
      height: 32,
      alignItems: "center",
      justifyContent: "center",
    },
    openBtn: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      paddingVertical: 10,
      paddingHorizontal: 16,
      borderRadius: 10,
      backgroundColor: t.primary,
    },
    openLabel: { fontSize: 14, fontWeight: "700", color: t.onPrimary },
  });
}
