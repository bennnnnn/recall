import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { VisualCard } from "@/components/rich/VisualCard";
import { parseChemistryScene, type ChemistryScene } from "@/lib/chemistry/scene";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Space } from "@/lib/space";

type Props = { content: string };

/** Draws a verified chemistry scene. It never computes a result. */
export function ChemistrySceneBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const scene = useMemo(() => parseChemistryScene(content), [content]);

  if (!scene) {
    return (
      <VisualCard label={t("rich.chemistry_structure")} icon="flask">
        <Text style={s.muted}>{t("rich.chemistry_invalid")}</Text>
      </VisualCard>
    );
  }

  return (
    <VisualCard label={scene.title} icon="flask">
      <SceneBody scene={scene} styles={s} />
    </VisualCard>
  );
}

function SceneBody({ scene, styles }: { scene: ChemistryScene; styles: ReturnType<typeof makeStyles> }) {
  if (scene.kind === "balance") {
    return (
      <View>
        {scene.rows.map((row) => (
          <Text key={row.element} style={styles.line}>
            {row.element}: {row.left} → {row.right}
          </Text>
        ))}
        <Text style={styles.muted}>
          charge {scene.charge.left} → {scene.charge.right}
        </Text>
      </View>
    );
  }
  if (scene.kind === "stoich") {
    return (
      <View>
        {scene.steps.map((step, index) => (
          <Text key={`${step.label}-${index}`} style={styles.line}>
            {index + 1}. {step.label} = {step.value}
          </Text>
        ))}
      </View>
    );
  }
  if (scene.kind === "vsepr") {
    const terminals = scene.terminals.join(" · ");
    return (
      <View>
        <Text style={styles.angle}>{scene.bond_angle}</Text>
        <Text style={styles.line}>
          {terminals} around {scene.central}
        </Text>
        <Text style={styles.line}>
          {scene.geometry}, {scene.lone_pairs} lone pairs
        </Text>
        <Text style={styles.muted}>
          {scene.electron_geometry}, ideal {scene.ideal_angle}
        </Text>
      </View>
    );
  }
  if (scene.kind === "titration") {
    return (
      <View>
        <Text style={styles.line}>{scene.region}</Text>
        {scene.anchors.map((anchor) => (
          <Text key={anchor.label} style={styles.line}>
            {anchor.label}
            {anchor.ph ? ` · pH ${anchor.ph}` : ""}
            {anchor.volume ? ` · ${anchor.volume}` : ""}
            {anchor.value ? ` · ${anchor.value}` : ""}
          </Text>
        ))}
      </View>
    );
  }
  if (scene.kind === "equilibrium") {
    return (
      <View>
        {scene.rows.map((row) => (
          <Text key={row.species} style={styles.line}>
            {row.species}: {row.initial} {row.change} → {row.equilibrium}
          </Text>
        ))}
      </View>
    );
  }
  return (
    <View>
      <Text style={styles.line}>anode {scene.anode}</Text>
      <Text style={styles.line}>cathode {scene.cathode}</Text>
      <Text style={styles.angle}>{scene.potential}</Text>
      <Text style={styles.muted}>electrons {scene.electrons}</Text>
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    line: { ...Type.callout, color: t.text, marginBottom: Space.xs },
    angle: { ...Type.title, ...Weight.semibold, color: t.text, marginBottom: Space.xs },
    muted: { ...Type.caption, color: t.textSecondary },
  });
}
