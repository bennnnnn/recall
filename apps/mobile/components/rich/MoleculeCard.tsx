/**
 * Combined 2D + optional 3D molecule card. Display-only ```molecule fences
 * (smiles paired with a following molecule3d) render here so the thread
 * does not stack two full cards.
 */
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { CopyButton } from "@/components/CopyButton";
import { VisualCard } from "@/components/rich/VisualCard";
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
      <VisualCard label={t("rich.chemistry_structure")} icon="flask-outline">
        <View style={s.previewBox}>
          <Text style={s.fallbackHint}>{t("rich.chemistry_invalid")}</Text>
        </View>
      </VisualCard>
    );
  }

  const active: Mode = show3d && mode === "3d" ? "3d" : "2d";
  const modeToggle = show3d ? (
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
  ) : undefined;

  return (
    <VisualCard
      label={t("rich.chemistry_structure")}
      icon="flask-outline"
      headerRight={modeToggle}
      actions={<CopyButton text={smiles} />}
    >
      {caption ? (
        <View style={s.captionBox}>
          <Text style={s.captionText}>{caption}</Text>
        </View>
      ) : null}

      {active === "3d" && sdf ? <Molecule3DView sdf={sdf} /> : <Chemistry2DView smiles={smiles} />}
    </VisualCard>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
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
  });
}
