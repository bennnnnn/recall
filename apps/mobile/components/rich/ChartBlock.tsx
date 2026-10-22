/**
 * Chart block — renders ```chart / ```vega / ```vega-lite / ```plot fences
 * inline via WebView + Vega-Embed so the user sees the actual chart, not raw JSON.
 */
import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import * as WebBrowser from "expo-web-browser";
import { Icon } from "@/ui/icons/Icon";

import { CopyButton } from "@/components/CopyButton";
import { useWebPreviewHeight } from "@/components/rich/useWebPreviewHeight";
import { VisualCard } from "@/components/rich/VisualCard";
import { useDeferredWebViewMount } from "@/hooks/useDeferredWebViewMount";
import { buildVegaHtml, VEGA_LIBRARIES } from "@/lib/chartPreviewHtml";
import { CHART_HEIGHT_EPSILON_PX, CHART_PREVIEW_HEIGHT } from "@/lib/chartPreviewHeight";
import { CODE_FONT } from "@/lib/fonts";
import { IconSize } from "@/ui/icons/sizes";
import { Theme, useTheme } from "@/lib/theme";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";
import { useVendorTexts } from "@/lib/vendorAssets";
import {
  getPreviewWebView,
  STATIC_HTML_ORIGIN_WHITELIST,
  useStaticOnlyNavigation,
} from "@/lib/webView";

type Props = { content: string };

export function ChartBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [showSource, setShowSource] = useState(false);
  const [viewWidth, setViewWidth] = useState(0);
  const { expanded, height, clipped, renderError, onMessage, toggleExpanded } =
    useWebPreviewHeight({
      rules: CHART_PREVIEW_HEIGHT,
      page: "chart",
      errorText: t("rich.chart_error"),
    });

  const plotWidth = viewWidth > 0 ? viewWidth - 16 : 320;
  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const canRenderInlineChart = previewWebView?.mode === "rnc";
  const libraries = useVendorTexts(VEGA_LIBRARIES, Boolean(WebView) && canRenderInlineChart);
  const vegaHtml = useMemo(
    () => (libraries.texts ? buildVegaHtml(content, theme, plotWidth, libraries.texts) : ""),
    [content, theme, plotWidth, libraries.texts],
  );
  const source = useMemo(() => ({ html: vegaHtml }), [vegaHtml]);
  const { canMount: canMountWebView, onLoaded } = useDeferredWebViewMount(
    Boolean(WebView) && canRenderInlineChart,
  );
  const canMount = canMountWebView && Boolean(vegaHtml);
  const chartError = renderError ?? (libraries.failed ? t("rich.chart_error") : null);
  const onShouldStartLoadWithRequest = useStaticOnlyNavigation(vegaHtml);

  const handleOpenVegaEditor = useCallback(async () => {
    await Clipboard.setStringAsync(content);
    await WebBrowser.openBrowserAsync("https://vega.github.io/editor/");
  }, [content]);

  return (
    <VisualCard
      label={t("rich.chart")}
      icon="bar-chart"
      headerRight={
        <Text style={s.lineCount}>
          {t("rich.lines_count", { count: content.trim().split("\n").length })}
        </Text>
      }
      onLayout={(e) => {
        const w = Math.floor(e.nativeEvent.layout.width);
        if (w > 0 && Math.abs(w - viewWidth) > CHART_HEIGHT_EPSILON_PX) setViewWidth(w);
      }}
      actions={
        <>
          <CopyButton text={content} />
          <Pressable
            style={s.iconBtn}
            onPress={() => setShowSource((v) => !v)}
            hitSlop={8}
            accessibilityRole="button"
            accessibilityLabel={t("rich.source")}
          >
            <Icon
              name={showSource ? "eye-off" : "code"}
              size={IconSize.sm}
              color={showSource ? theme.primary : theme.textSecondary}
            />
          </Pressable>
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
          <Pressable
            style={s.iconBtn}
            onPress={handleOpenVegaEditor}
            hitSlop={8}
            accessibilityRole="button"
            accessibilityLabel={t("rich.vega_editor")}
          >
            <Icon name="external-link" size={IconSize.sm} color={theme.textSecondary} />
          </Pressable>
        </>
      }
    >
      <View style={[s.previewBox, { height }]}>
        {chartError ? (
          <View style={[s.previewPlaceholder, { height }]}>
            <Icon name="alert-circle" size={IconSize.sm} color={theme.danger} />
            <Text style={[s.previewPlaceholderText, { color: theme.danger }]}>
              {chartError}
            </Text>
          </View>
        ) : WebView && canRenderInlineChart ? (
          canMount ? (
            <WebView
              originWhitelist={STATIC_HTML_ORIGIN_WHITELIST}
              source={source}
              style={{ height, width: viewWidth > 0 ? viewWidth : 320 }}
              scrollEnabled={clipped}
              nestedScrollEnabled={clipped}
              showsVerticalScrollIndicator={clipped}
              javaScriptEnabled
              domStorageEnabled={false}
              onLoadEnd={onLoaded}
              onMessage={onMessage}
              onShouldStartLoadWithRequest={onShouldStartLoadWithRequest}
            />
          ) : (
            <View style={[s.previewPlaceholder, { height }]}>
              <ActivityIndicator color={theme.primary} />
            </View>
          )
        ) : (
          <View style={[s.previewPlaceholder, { height }]}>
            <Text style={s.previewPlaceholderText}>
              {t("rich.chart_dev_build")}
            </Text>
          </View>
        )}
      </View>

      {showSource && (
        <View style={s.sourceBox}>
          <Text style={s.sourceText} selectable>
            {content.trim()}
          </Text>
        </View>
      )}
    </VisualCard>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    lineCount: { ...Type.meta, color: t.textTertiary },
    previewBox: {
      backgroundColor: t.bg,
      overflow: "hidden",
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
    },
    previewPlaceholder: {
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: Space.md,
    },
    previewPlaceholderText: {
      ...Type.compact,
      color: t.textSecondary,
      textAlign: "center",
    },
    sourceBox: {
      paddingHorizontal: Space.sm,
      paddingVertical: Space.sm,
      backgroundColor: t.contentSurface,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
      maxHeight: 200,
    },
    sourceText: { ...Type.meta, fontFamily: CODE_FONT, lineHeight: 18, color: t.textSecondary },
    iconBtn: {
      width: 32,
      height: 32,
      alignItems: "center",
      justifyContent: "center",
    },
  });
}
