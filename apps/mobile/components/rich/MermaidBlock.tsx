/**
 * Mermaid diagram — inline SVG render via WebView (dev build), with source fallback.
 */
import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import * as WebBrowser from "expo-web-browser";
import { Icon } from "@/ui/icons/Icon";

import { CopyButton } from "@/components/CopyButton";
import { usePreviewPage } from "@/components/rich/usePreviewPage";
import { useWebPreviewHeight } from "@/components/rich/useWebPreviewHeight";
import { VisualCard } from "@/components/rich/VisualCard";
import { useDeferredWebViewMount } from "@/hooks/useDeferredWebViewMount";
import { CODE_FONT } from "@/lib/fonts";
import { MERMAID_MIN_HEIGHT, MERMAID_PREVIEW_HEIGHT } from "@/lib/mermaidPreviewHeight";
import { MERMAID_PAGE, mermaidPreviewConfig } from "@/lib/mermaidPreviewHtml";
import { sanitizeMermaidNodeLabels } from "@/lib/mermaidSanitize";
import { Theme, useTheme } from "@/lib/theme";
import { getPreviewWebView } from "@/lib/webView";
import { IconSize } from "@/ui/icons/sizes";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Type, Weight } from "@/lib/type";

type Props = { content: string };

export function MermaidBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [showSource, setShowSource] = useState(false);
  const { expanded, height, clipped, renderError, onMessage, toggleExpanded } =
    useWebPreviewHeight({
      rules: MERMAID_PREVIEW_HEIGHT,
      page: "mermaid",
      errorText: t("rich.mermaid_error"),
    });

  const sanitized = useMemo(() => sanitizeMermaidNodeLabels(content.trim()), [content]);
  const config = useMemo(() => mermaidPreviewConfig(sanitized, theme), [sanitized, theme]);
  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const canRenderInline = previewWebView?.mode === "rnc";
  const preview = usePreviewPage(MERMAID_PAGE, config, Boolean(WebView) && canRenderInline);
  const { canMount, onLoaded } = useDeferredWebViewMount(
    Boolean(WebView) && canRenderInline && preview.status === "ready",
  );
  const previewError = preview.status === "failed" ? t("rich.mermaid_error") : null;

  const handleOpenLiveEditor = useCallback(async () => {
    await Clipboard.setStringAsync(sanitized);
    await WebBrowser.openBrowserAsync("https://mermaid.live/edit");
  }, [sanitized]);

  return (
    <VisualCard
      label={t("rich.mermaid_diagram")}
      icon="network"
      headerRight={
        <Pressable
          onPress={() => setShowSource((v) => !v)}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel={showSource ? t("rich.diagram") : t("rich.source")}
        >
          <Icon
            name={showSource ? "eye-off" : "code"}
            size={IconSize.sm}
            color={theme.primary}
          />
        </Pressable>
      }
      actions={
        <>
          <CopyButton text={sanitized} />
          {clipped || expanded ? (
            <Pressable
              style={s.iconBtn}
              onPress={toggleExpanded}
              hitSlop={8}
              accessibilityRole="button"
              accessibilityLabel={expanded ? t("rich.collapse") : t("rich.expand")}
            >
              <Icon
                name={expanded ? "collapse" : "expand"}
                size={IconSize.sm}
                color={theme.textSecondary}
              />
            </Pressable>
          ) : null}
          <Pressable style={s.openBtn} onPress={handleOpenLiveEditor} hitSlop={8}>
            <Icon name="external-link" size={IconSize.sm} color={theme.onPrimary} />
            <Text style={s.openLabel}>{t("rich.mermaid_live")}</Text>
          </Pressable>
        </>
      }
    >
      {renderError || previewError ? (
        <View style={s.previewBox}>
          <Icon name="alert-circle" size={IconSize.sm} color={theme.danger} />
          <Text style={[s.previewText, { color: theme.danger }]}>
            {renderError ?? previewError}
          </Text>
        </View>
      ) : showSource ? (
        <View style={s.previewBox}>
          <Text style={s.previewText}>{sanitized}</Text>
        </View>
      ) : canRenderInline && WebView ? (
        canMount && preview.status === "ready" ? (
          <View style={[s.webWrap, { height }]}>
            <WebView
              key={preview.webViewKey}
              {...preview.webViewProps}
              scrollEnabled={clipped}
              nestedScrollEnabled={clipped}
              showsVerticalScrollIndicator={clipped}
              bounces={false}
              overScrollMode="never"
              style={s.webview}
              javaScriptEnabled
              domStorageEnabled={false}
              onLoadEnd={onLoaded}
              onMessage={onMessage}
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
            {sanitized}
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
      paddingHorizontal: Space.sm,
      paddingVertical: Space.sm,
      backgroundColor: t.contentSurface,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
    },
    previewText: { ...Type.meta, fontFamily: CODE_FONT, lineHeight: 18, color: t.textSecondary },
    fallbackHint: { ...Type.meta, color: t.textTertiary, marginTop: Space.xs },
    iconBtn: {
      width: 32,
      height: 32,
      alignItems: "center",
      justifyContent: "center",
    },
    openBtn: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      paddingVertical: Space.sm,
      paddingHorizontal: Space.md,
      borderRadius: Radius.sm,
      backgroundColor: t.primary,
    },
    openLabel: { ...Type.label, ...Weight.bold, color: t.onPrimary },
  });
}
