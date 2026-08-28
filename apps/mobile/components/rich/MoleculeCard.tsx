/**
 * Combined 2D + optional 3D molecule card. Display-only ```molecule fences
 * (smiles paired with a following molecule3d) render here so the thread
 * does not stack two full cards.
 */
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/components/Icon";
import { CopyButton } from "@/components/CopyButton";
import { Chemistry2DView } from "@/components/rich/ChemistryBlock";
import { Molecule3DView } from "@/components/rich/Molecule3DBlock";
import { parseMoleculeFence } from "@/lib/moleculePair";
import { parseMolGeometry, parseMolecule3DFence } from "@/lib/molecule3dFence";
import { Theme, useTheme } from "@/lib/theme";

type Mode = "2d" | "3d";

export function MoleculeCard({ content }: { content: string }) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [mode, setMode] = useState<Mode>("2d");

  const parsed = useMemo(() => parseMoleculeFence(content), [content]);
  const smiles = parsed?.smiles ?? "";
  const caption = parsed?.caption;
  const sdf = useMemo(() => {
    const raw = parsed?.sdf;
    if (!raw) return null;
    const mol = parseMolecule3DFence(raw);
    if (!mol?.sdf || !parseMolGeometry(mol.sdf)) return null;
    return mol.sdf;
  }, [parsed]);
  const show3d = Boolean(sdf);

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

  const active: Mode = show3d && mode === "3d" ? "3d" : "2d";

  return (
    <View style={s.wrap}>
      <View style={s.header}>
        <View style={s.headerLeft}>
          <Icon name="flask-outline" size={16} color={theme.primary} />
          <Text style={s.headerLabel}>{t("rich.chemistry_structure")}</Text>
        </View>
        {show3d ? (
          <View style={s.toggle}>
            <Pressable
              style={[s.toggleBtn, active === "2d" && s.toggleBtnActive]}
              onPress={() => setMode("2d")}
              testID="molecule-mode-2d"
              accessibilityRole="button"
              accessibilityState={{ selected: active === "2d" }}
              accessibilityLabel={t("rich.chemistry_2d")}
            >
              <Text style={[s.toggleText, active === "2d" && s.toggleTextActive]}>
                {t("rich.chemistry_2d")}
              </Text>
            </Pressable>
            <Pressable
              style={[s.toggleBtn, active === "3d" && s.toggleBtnActive]}
              onPress={() => setMode("3d")}
              testID="molecule-mode-3d"
              accessibilityRole="button"
              accessibilityState={{ selected: active === "3d" }}
              accessibilityLabel={t("rich.chemistry_3d")}
            >
              <Text style={[s.toggleText, active === "3d" && s.toggleTextActive]}>
                {t("rich.chemistry_3d")}
              </Text>
            </Pressable>
          </View>
        ) : null}
      </View>

      {caption ? (
        <View style={s.captionBox}>
          <Text style={s.captionText}>{caption}</Text>
        </View>
      ) : null}

      {active === "3d" && sdf ? <Molecule3DView sdf={sdf} /> : <Chemistry2DView smiles={smiles} />}

      <View style={s.actions}>
        <CopyButton text={smiles} />
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
      gap: 8,
    },
    headerLeft: { flexDirection: "row", alignItems: "center", gap: 8, flexShrink: 1 },
    headerLabel: { fontSize: 14, fontWeight: "700", color: t.text },
    toggle: { flexDirection: "row", gap: 4 },
    toggleBtn: {
      paddingHorizontal: 10,
      paddingVertical: 5,
      borderRadius: 8,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      backgroundColor: t.bg,
    },
    toggleBtnActive: {
      backgroundColor: t.primary,
      borderColor: t.primary,
    },
    toggleText: { fontSize: 11, fontWeight: "600", color: t.textSecondary },
    toggleTextActive: { color: t.onPrimary },
    captionBox: {
      paddingHorizontal: 14,
      paddingTop: 8,
      paddingBottom: 0,
      backgroundColor: t.bg,
    },
    captionText: { fontSize: 13, fontWeight: "600", color: t.textSecondary },
    previewBox: {
      paddingHorizontal: 14,
      paddingVertical: 24,
      backgroundColor: t.contentSurface,
      alignItems: "center",
    },
    fallbackHint: { fontSize: 13, color: t.textTertiary, textAlign: "center" },
    actions: { flexDirection: "row", gap: 10, paddingHorizontal: 14, paddingVertical: 10 },
  });
}
