import React, { Suspense, useMemo, useState } from "react";
import { StyleSheet, TouchableOpacity, View } from "react-native";
import { useTranslation } from "react-i18next";
import { Ionicons } from "@expo/vector-icons";

import { CodeBlock } from "@/components/CodeBlock";
import { bundleHtmlPreview, previewHasSiblingAssets } from "@/lib/htmlPreviewBundle";
import { useHtmlPreviewFiles } from "@/lib/htmlPreviewFiles";
import { openHtmlInBrowser } from "@/lib/openHtmlPreview";
import { Theme, useTheme } from "@/lib/theme";

const HtmlPreviewModalLazy = React.lazy(() =>
  import("@/components/HtmlPreviewModal").then((m) => ({
    default: m.HtmlPreviewModal,
  })),
);

type Props = {
  code: string;
  lang?: string;
};

/** HTML fence: syntax-highlighted code + preview modal + bottom actions. */
export function WebPreviewCodeBlock({ code, lang = "html" }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [modalOpen, setModalOpen] = useState(false);
  const siblingFiles = useHtmlPreviewFiles();
  const previewHtml = useMemo(
    () => bundleHtmlPreview(code, siblingFiles),
    [code, siblingFiles],
  );
  const previewLabel = previewHasSiblingAssets(siblingFiles)
    ? t("preview.preview_html_bundled")
    : t("preview.preview_html");

  return (
    <>
      <CodeBlock
        code={code}
        lang={lang}
        headerExtra={
          <TouchableOpacity
            style={[s.iconBtn, modalOpen && s.iconBtnActive]}
            onPress={() => setModalOpen(true)}
            activeOpacity={0.6}
            hitSlop={4}
            accessibilityRole="button"
            accessibilityLabel={previewLabel}
          >
            <Ionicons
              name="play-outline"
              size={16}
              color={modalOpen ? theme.primary : theme.textSecondary}
            />
          </TouchableOpacity>
        }
        footerExtra={
          <View style={s.footerActions}>
            <TouchableOpacity
              style={s.iconBtn}
              onPress={() => setModalOpen(true)}
              activeOpacity={0.6}
              hitSlop={4}
              accessibilityRole="button"
              accessibilityLabel={previewLabel}
            >
              <Ionicons name="play-outline" size={18} color={theme.textSecondary} />
            </TouchableOpacity>
            <TouchableOpacity
              style={s.iconBtn}
              onPress={() => void openHtmlInBrowser(previewHtml)}
              activeOpacity={0.6}
              hitSlop={4}
              accessibilityRole="button"
              accessibilityLabel={t("preview.open_in_browser")}
            >
              <Ionicons name="open-outline" size={18} color={theme.textSecondary} />
            </TouchableOpacity>
          </View>
        }
      />

      {modalOpen ? (
        <Suspense fallback={null}>
          <HtmlPreviewModalLazy visible html={previewHtml} onClose={() => setModalOpen(false)} />
        </Suspense>
      ) : null}
    </>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    footerActions: {
      flexDirection: "row",
      alignItems: "center",
      gap: 4,
    },
    iconBtn: {
      width: 44,
      height: 44,
      borderRadius: 8,
      alignItems: "center",
      justifyContent: "center",
    },
    iconBtnActive: {
      backgroundColor: t.primaryLight,
    },
  });
}
