/**
 * 3D molecule viewer — renders SDF/MOL blocks via vendored 3Dmol.js in a
 * sandboxed WebView (same offline/CSP pattern as ChemistryBlock).
 * Supports rotate/zoom via touch; styled to match the 2D SMILES card.
 */
import { useMemo, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/components/Icon";
import { CopyButton } from "@/components/CopyButton";
import { useDeferredWebViewMount } from "@/hooks/useDeferredWebViewMount";
import { parseMolecule3DFence } from "@/lib/molecule3dFence";
import { injectPreviewCsp, inlineScript } from "@/lib/previewSandbox";
import { Theme, useTheme } from "@/lib/theme";
import { THREE_D_MOL_MIN_JS } from "@/lib/vendor/threeDMolMinJs";
import {
  getPreviewWebView,
  STATIC_HTML_ORIGIN_WHITELIST,
  useStaticOnlyNavigation,
} from "@/lib/webView";

type Props = { content: string };

const PREVIEW_HEIGHT = 280;

type MoleculeStyle = "ball-stick" | "spacefill" | "wireframe" | "cartoon";

const STYLE_CONFIG: Record<MoleculeStyle, string> = {
  "ball-stick": "{ stick: { radius: 0.14 }, sphere: { scale: 0.28 } }",
  spacefill: "{ sphere: { scale: 0.32 } }",
  wireframe: "{ stick: { radius: 0.06, wireframe: true }, sphere: { scale: 0.12 } }",
  cartoon: "{ cartoon: { } }",
};

function escapeJsString(value: string): string {
  return value
    .replace(/\\/g, "\\\\")
    .replace(/`/g, "\\`")
    .replace(/\$/g, "\\$")
    .replace(/<\/script>/gi, "<\\/script>");
}

function buildMolecule3dHtml(sdf: string, theme: Theme, style: MoleculeStyle): string {
  const safeSdf = escapeJsString(sdf.trim());
  const bgColor = theme.isDark ? "#1a1a2e" : "#ffffff";
  const styleConfig = STYLE_CONFIG[style];
  // 3Dmol.js is a UMD bundle. We eval it into the global scope, then use
  // the global `M` / `$3Dmol` object.
  const loader = `eval(\`${THREE_D_MOL_MIN_JS}\`);\n`;
  const run =
    "(function() {\n" +
    "  var sdf = `" +
    safeSdf +
    "`;\n" +
    "  function reportError(msg) {\n" +
    "    try { window.ReactNativeWebView && window.ReactNativeWebView.postMessage(JSON.stringify({ kind: 'molecule3d-error', message: msg })); } catch (e) {}\n" +
    "    var err = document.getElementById('err');\n" +
    "    err.textContent = msg;\n" +
    "    err.style.display = 'block';\n" +
    "    var viewer = document.getElementById('viewer');\n" +
    "    if (viewer) viewer.style.display = 'none';\n" +
    "  }\n" +
    "  var M = (typeof $3Dmol !== 'undefined') ? $3Dmol : (typeof window.M !== 'undefined' ? window.M : null);\n" +
    "  if (!M || typeof M.createViewer !== 'function') {\n" +
    "    reportError('3D molecule renderer unavailable.');\n" +
    "    return;\n" +
    "  }\n" +
    "  try {\n" +
    "    var viewer = M.createViewer('viewer', { backgroundColor: '" +
    bgColor +
    "', antialias: true });\n" +
    "    viewer.addModel(sdf, 'sdf');\n" +
    "    viewer.setStyle({}, " + styleConfig + ");\n" +
    "    viewer.zoomTo();\n" +
    "    viewer.render();\n" +
    "  } catch (e) {\n" +
    "    reportError('Could not render that 3D structure.');\n" +
    "  }\n" +
    "})();\n";
  return injectPreviewCsp(
    "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"UTF-8\">" +
      '<meta name="viewport" content="width=device-width, initial-scale=1.0">' +
      "<style>body{margin:0;padding:0;background:" +
      bgColor +
      ";overflow:hidden}" +
      "#viewer{width:100%;height:" +
      PREVIEW_HEIGHT +
      "px}" +
      "#err{color:" +
      theme.danger +
      ";font-size:13px;display:none;white-space:pre-wrap;padding:16px;text-align:center}</style>" +
      "</head><body>" +
      '<div id="viewer"></div><div id="err"></div>' +
      "<script>" +
      inlineScript(loader + run) +
      "</script></body></html>",
  );
}

export function Molecule3DBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [style, setStyle] = useState<MoleculeStyle>("ball-stick");

  const parsed = useMemo(() => parseMolecule3DFence(content), [content]);
  const sdf = parsed?.sdf ?? "";
  const caption = parsed?.caption;

  const html = useMemo(
    () => (sdf ? buildMolecule3dHtml(sdf, theme, style) : ""),
    [sdf, theme, style],
  );
  const webSource = useMemo(() => ({ html }), [html]);
  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const canRenderInline = previewWebView?.mode === "rnc" && Boolean(sdf);
  const { canMount, onLoaded } = useDeferredWebViewMount(Boolean(WebView) && canRenderInline);
  const onShouldStartLoadWithRequest = useStaticOnlyNavigation(html);

  const handleWebViewMessage = useCallback((event: { nativeEvent: { data?: string } }) => {
    try {
      const data = JSON.parse(event.nativeEvent.data ?? "{}");
      if (data && data.kind === "molecule3d-error") setRenderError(data.message ?? t("rich.chemistry_invalid"));
    } catch {
      setRenderError(t("rich.chemistry_invalid"));
    }
  }, [t]);

  if (!parsed) {
    return (
      <View style={s.wrap}>
        <View style={s.header}>
          <View style={s.headerLeft}>
            <Icon name="flask-outline" size={16} color={theme.primary} />
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
          <Icon name="flask-outline" size={16} color={theme.primary} />
          <Text style={s.headerLabel}>{t("rich.chemistry_structure")}</Text>
        </View>
      </View>

      {caption ? (
        <View style={s.captionBox}>
          <Text style={s.captionText}>{caption}</Text>
        </View>
      ) : null}

      {renderError ? (
        <View style={s.previewBox}>
          <Icon name="alert-circle-outline" size={20} color={theme.danger} />
          <Text style={[s.fallbackHint, { color: theme.danger }]}>
            {renderError}
          </Text>
        </View>
      ) : canRenderInline && WebView ? (
        canMount ? (
          <View style={s.webWrap}>
            <WebView
              originWhitelist={STATIC_HTML_ORIGIN_WHITELIST}
              source={webSource}
              scrollEnabled={false}
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
          <Icon name="flask-outline" size={28} color={theme.textTertiary} />
          <Text style={s.fallbackHint}>
            {caption ? `${caption}\n` : ""}
            {t("rich.chemistry_3d_dev_build")}
          </Text>
        </View>
      )}

      <View style={s.actions}>
        {canRenderInline && WebView ? (
          <View style={s.styleRow}>
            {(["ball-stick", "spacefill", "wireframe"] as const).map((st) => (
              <Pressable
                key={st}
                style={[s.styleBtn, style === st && s.styleBtnActive]}
                onPress={() => setStyle(st)}
              >
                <Text style={[s.styleBtnText, style === st && s.styleBtnTextActive]}>
                  {st === "ball-stick" ? "Ball" : st === "spacefill" ? "Sphere" : "Wire"}
                </Text>
              </Pressable>
            ))}
          </View>
        ) : null}
        <CopyButton text={sdf} variant="action" />
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
      paddingVertical: 24,
      backgroundColor: t.contentSurface,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
      alignItems: "center",
      gap: 8,
    },
    fallbackHint: { fontSize: 13, color: t.textTertiary, textAlign: "center" },
    actions: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 10, paddingHorizontal: 14, paddingVertical: 10 },
    styleRow: { flexDirection: "row", gap: 6 },
    styleBtn: {
      paddingHorizontal: 10,
      paddingVertical: 5,
      borderRadius: 8,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      backgroundColor: t.surface,
    },
    styleBtnActive: {
      backgroundColor: t.primary,
      borderColor: t.primary,
    },
    styleBtnText: { fontSize: 11, fontWeight: "600", color: t.textSecondary },
    styleBtnTextActive: { color: "#fff" },
  });
}
