/**
 * Chemistry structure — SMILES rendered via vendored SmilesDrawer in a
 * sandboxed WebView (same offline/CSP pattern as Mermaid).
 */
import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import { CopyButton } from "@/components/CopyButton";
import { MoleculeCaption, MoleculeNote } from "@/components/rich/MoleculeChrome";
import { VisualCard } from "@/components/rich/VisualCard";
import { useDeferredWebViewMount } from "@/hooks/useDeferredWebViewMount";
import { parseChemistryFence } from "@/lib/chemistry/fence";
import {
  buildSmilesDrawerHtml,
  readSmilesDrawerError,
  type SmilesDrawerError,
} from "@/lib/chemistry/smilesDrawerHtml";
import { CODE_FONT } from "@/lib/fonts";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";
import {
  getPreviewWebView,
  STATIC_HTML_ORIGIN_WHITELIST,
  useStaticOnlyNavigation,
} from "@/lib/webView";

type Props = { content: string };

const PREVIEW_HEIGHT = 160;

const ERROR_KEY: Record<SmilesDrawerError, string> = {
  unavailable: "rich.chemistry_renderer_unavailable",
  render: "rich.chemistry_invalid",
};

/** 2D SMILES preview without card chrome — used by ChemistryBlock and MoleculeCard. */
export function Chemistry2DView({ smiles }: { smiles: string }) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  // Keyed by the SMILES it failed on, so a new structure starts clean without an effect.
  const [failure, setFailure] = useState<{ smiles: string; code: SmilesDrawerError } | null>(null);
  const renderError = failure?.smiles === smiles ? failure.code : null;

  const html = useMemo(
    () => (smiles ? buildSmilesDrawerHtml(smiles, theme) : ""),
    [smiles, theme],
  );
  const webSource = useMemo(() => ({ html }), [html]);
  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const canRenderInline = previewWebView?.mode === "rnc" && Boolean(smiles);
  const { canMount, onLoaded } = useDeferredWebViewMount(Boolean(WebView) && canRenderInline);
  const onShouldStartLoadWithRequest = useStaticOnlyNavigation(html);

  const handleWebViewMessage = useCallback(
    (event: { nativeEvent: { data?: string } }) => {
      const code = readSmilesDrawerError(event.nativeEvent.data);
      if (code) setFailure({ smiles, code });
    },
    [smiles],
  );

  if (renderError) {
    return (
      <View style={s.previewBox}>
        <Icon name="alert-circle" size={IconSize.sm} color={theme.danger} />
        <Text style={[s.previewText, { color: theme.danger }]}>{t(ERROR_KEY[renderError])}</Text>
      </View>
    );
  }
  if (canRenderInline && WebView) {
    if (!canMount) {
      return (
        <View style={s.loadingWrap}>
          <ActivityIndicator color={theme.primary} />
        </View>
      );
    }
    return (
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
    );
  }
  return (
    <View style={s.previewBox}>
      <Text style={s.previewText}>{smiles}</Text>
      <Text style={s.fallbackHint}>{t("rich.chemistry_dev_build")}</Text>
    </View>
  );
}

export function ChemistryBlock({ content }: Props) {
  const { t } = useTranslation();

  const parsed = useMemo(() => parseChemistryFence(content), [content]);
  const smiles = parsed?.smiles ?? "";
  const caption = parsed?.caption;

  if (!parsed) {
    return (
      <VisualCard label={t("rich.chemistry_structure")} icon="flask">
        <MoleculeNote text={t("rich.chemistry_invalid")} />
      </VisualCard>
    );
  }

  return (
    <VisualCard
      label={t("rich.chemistry_structure")}
      icon="flask"
      actions={<CopyButton text={smiles} accessibilityLabel={t("rich.chemistry_copy_smiles")} />}
    >
      {caption ? <MoleculeCaption text={caption} /> : null}

      <Chemistry2DView smiles={smiles} />
    </VisualCard>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    webWrap: { height: PREVIEW_HEIGHT, backgroundColor: t.bg },
    webview: { flex: 1, backgroundColor: "transparent" },
    loadingWrap: {
      height: PREVIEW_HEIGHT,
      backgroundColor: t.bg,
      alignItems: "center",
      justifyContent: "center",
    },
    previewBox: {
      paddingHorizontal: Space.sm + 2,
      paddingVertical: Space.xs + 2,
      backgroundColor: t.contentSurface,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
    },
    previewText: { fontFamily: CODE_FONT, ...Type.meta, lineHeight: 17, color: t.textSecondary },
    fallbackHint: { ...Type.meta, color: t.textTertiary, marginTop: Space.xs },
  });
}
