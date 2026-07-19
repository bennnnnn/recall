/**
 * Chemistry structure — SMILES rendered via vendored SmilesDrawer in a
 * sandboxed WebView (same offline/CSP pattern as Mermaid).
 */
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { CopyButton } from "@/components/CopyButton";
import { useDeferredWebViewMount } from "@/hooks/useDeferredWebViewMount";
import { parseChemistryFence } from "@/lib/chemistryFence";
import { CODE_FONT } from "@/lib/fonts";
import { injectPreviewCsp, inlineScript } from "@/lib/previewSandbox";
import { Theme, useTheme } from "@/lib/theme";
import { SMILES_DRAWER_MIN_JS } from "@/lib/vendor/smilesDrawerMinJs";
import {
  getPreviewWebView,
  STATIC_HTML_ORIGIN_WHITELIST,
  useStaticOnlyNavigation,
} from "@/lib/webView";

type Props = { content: string };

const PREVIEW_HEIGHT = 160;
const DRAW_WIDTH = 240;
const DRAW_HEIGHT = 140;

function escapeJsString(value: string): string {
  return value
    .replace(/\\/g, "\\\\")
    .replace(/`/g, "\\`")
    .replace(/\$/g, "\\$")
    .replace(/<\/script>/gi, "<\\/script>");
}

function buildChemistryHtml(smiles: string, theme: Theme): string {
  const safeSmiles = escapeJsString(smiles.trim());
  const themeName = theme.isDark ? "dark" : "light";
  // Concat (not template interpolate) so `${` inside the browserify bundle
  // cannot break this file. Bundle returns require(); entry id is 1.
  const loader =
    "var __sdReq = " + SMILES_DRAWER_MIN_JS + "\nvar SmilesDrawer = __sdReq(1);\n";
  // SmilesDrawer.Drawer.draw(..., infoOnly) incorrectly forwards infoOnly as
  // SvgDrawer weights (weights.every throws). Use SvgDrawer on an <svg> target
  // and omit weights/infoOnly so defaults apply.
  const run =
    "(function() {\n" +
    "  var smiles = `" +
    safeSmiles +
    "`;\n" +
    "  var err = document.getElementById('err');\n" +
    "  var root = document.getElementById('molecule');\n" +
    "  function fail(msg) {\n" +
    "    root.style.display = 'none';\n" +
    "    err.textContent = msg;\n" +
    "    err.style.display = 'block';\n" +
    "  }\n" +
    "  if (!SmilesDrawer || typeof SmilesDrawer.SvgDrawer !== 'function' || typeof SmilesDrawer.parse !== 'function') {\n" +
    "    fail('Chemistry renderer unavailable.');\n" +
    "    return;\n" +
    "  }\n" +
    "  var drawer = new SmilesDrawer.SvgDrawer({ width: " +
    DRAW_WIDTH +
    ", height: " +
    DRAW_HEIGHT +
    " });\n" +
    "  SmilesDrawer.parse(smiles, function(tree) {\n" +
    "    try { drawer.draw(tree, root, '" +
    themeName +
    "'); }\n" +
    "    catch (e) { fail('Could not render that structure.'); }\n" +
    "  }, function() { fail('Could not render that structure.'); });\n" +
    "})();\n";
  return injectPreviewCsp(
    "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"UTF-8\">" +
      '<meta name="viewport" content="width=device-width, initial-scale=1.0">' +
      "<style>body{margin:0;padding:4px;background:" +
      theme.bg +
      ";display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:" +
      DRAW_HEIGHT +
      "px}" +
      "svg{max-width:100%;height:auto;display:block}" +
      "#err{color:" +
      theme.danger +
      ";font-size:12px;display:none;white-space:pre-wrap;padding:8px;text-align:center}</style>" +
      "</head><body>" +
      '<svg id="molecule" xmlns="http://www.w3.org/2000/svg" width="' +
      DRAW_WIDTH +
      '" height="' +
      DRAW_HEIGHT +
      '"></svg><div id="err"></div>' +
      "<script>" +
      inlineScript(loader + run) +
      "</script></body></html>",
  );
}

export function ChemistryBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);

  const parsed = useMemo(() => parseChemistryFence(content), [content]);
  const smiles = parsed?.smiles ?? "";
  const caption = parsed?.caption;

  const html = useMemo(
    () => (smiles ? buildChemistryHtml(smiles, theme) : ""),
    [smiles, theme],
  );
  const webSource = useMemo(() => ({ html }), [html]);
  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const canRenderInline = previewWebView?.mode === "rnc" && Boolean(smiles);
  const { canMount, onLoaded } = useDeferredWebViewMount(Boolean(WebView) && canRenderInline);
  const onShouldStartLoadWithRequest = useStaticOnlyNavigation(html);

  if (!parsed) {
    return (
      <View style={s.wrap}>
        <View style={s.header}>
          <View style={s.headerLeft}>
            <Ionicons name="flask-outline" size={16} color={theme.primary} />
            <Text style={s.headerLabel}>{t("rich.chemistry_structure")}</Text>
          </View>
        </View>
        <View style={s.previewBox}>
          <Text style={s.fallbackHint}>{t("rich.chemistry_invalid")}</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={s.wrap}>
      <View style={s.header}>
        <View style={s.headerLeft}>
          <Ionicons name="flask-outline" size={16} color={theme.primary} />
          <Text style={s.headerLabel}>{t("rich.chemistry_structure")}</Text>
        </View>
      </View>

      {caption ? (
        <View style={s.captionBox}>
          <Text style={s.captionText}>{caption}</Text>
        </View>
      ) : null}

      {canRenderInline && WebView ? (
        canMount ? (
          <View style={s.webWrap}>
            <WebView
              originWhitelist={STATIC_HTML_ORIGIN_WHITELIST}
              source={webSource}
              scrollEnabled={false}
              style={s.webview}
              javaScriptEnabled
              onLoadEnd={onLoaded}
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
          <Text style={s.previewText}>{smiles}</Text>
          <Text style={s.fallbackHint}>{t("rich.chemistry_dev_build")}</Text>
        </View>
      )}

      <View style={s.actions}>
        <CopyButton text={smiles} variant="action" />
      </View>
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: {
      marginVertical: 8,
      borderRadius: 14,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      overflow: "hidden",
      backgroundColor: t.bg,
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: 14,
      paddingVertical: 10,
      backgroundColor: t.surface,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
    },
    headerLeft: { flexDirection: "row", alignItems: "center", gap: 8 },
    headerLabel: { fontSize: 14, fontWeight: "700", color: t.text },
    captionBox: {
      paddingHorizontal: 14,
      paddingTop: 8,
      paddingBottom: 0,
      backgroundColor: t.bg,
    },
    captionText: { fontSize: 13, fontWeight: "600", color: t.textSecondary },
    webWrap: { height: PREVIEW_HEIGHT, backgroundColor: t.bg },
    webview: { flex: 1, backgroundColor: "transparent" },
    loadingWrap: {
      height: PREVIEW_HEIGHT,
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
    actions: { flexDirection: "row", gap: 10, paddingHorizontal: 14, paddingVertical: 10 },
  });
}
