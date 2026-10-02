/**
 * 3D molecule viewer — native-first Skia ball-and-stick from SDF coordinates.
 * A WebView WebGL viewer stays blank in WKWebView (CSP / zero-size canvas), so we
 * project the same 3D coords that RDKit already computed. Expo Go and stale
 * native clients safely use the matching SVG renderer.
 */
import { lazy, Suspense, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { PanResponder, StyleSheet, View } from "react-native";
import Svg, { Circle, G, Line, Text as SvgText } from "react-native-svg";

import { CopyButton } from "@/components/CopyButton";
import { MoleculeCaption, MoleculeNote } from "@/components/rich/MoleculeChrome";
import {
  atomColor,
  atomLabelColor,
  bondStrokeWidth,
  layoutMolecule,
  showsAtomLabel,
  MOLECULE_PREVIEW_HEIGHT,
  type MoleculeStyle,
} from "@/lib/chemistry/molecule3dLayout";
import { VisualCard } from "@/components/rich/VisualCard";
import {
  parseMolGeometry,
  parseMolecule3DFence,
  type MolGeometry,
} from "@/lib/chemistry/molecule3dFence";
import { CODE_FONT } from "@/lib/fonts";
import { isSkiaAvailable } from "@/lib/skiaAvailability";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { SegmentedControl } from "@/ui/controls/SegmentedControl";

type Props = { content: string };

const SkiaMoleculeCanvasLazy = lazy(() =>
  import("@/components/rich/skia/SkiaMoleculeCanvas").then((module) => ({
    default: module.SkiaMoleculeCanvas,
  })),
);

type MoleculeCanvasProps = {
  geom: MolGeometry;
  style: MoleculeStyle;
  theme: Theme;
  yaw: number;
  pitch: number;
  width: number;
};

function SvgMoleculeCanvas({ geom, style, theme, yaw, pitch, width }: MoleculeCanvasProps) {
  const { t } = useTranslation();
  const height = MOLECULE_PREVIEW_HEIGHT;
  const laidOut = useMemo(
    () => layoutMolecule(geom, yaw, pitch, width, height, style),
    [geom, height, pitch, style, width, yaw],
  );

  return (
    <Svg
      testID="molecule-svg-fallback"
      width={width}
      height={height}
      accessibilityLabel={t("rich.chemistry_3d_a11y")}
    >
      {laidOut.drawOrder.map((item) => {
        if (item.kind === "bond") {
          const bond = laidOut.bonds[item.index]!;
          return (
            <Line
              key={`bond-${bond.key}`}
              x1={bond.x1}
              y1={bond.y1}
              x2={bond.x2}
              y2={bond.y2}
              stroke={theme.text}
              strokeWidth={bondStrokeWidth(style)}
              strokeLinecap="round"
            />
          );
        }
        const atom = laidOut.atoms[item.index]!;
        return (
          <G key={`atom-${atom.index}`}>
            <Circle cx={atom.x} cy={atom.y} r={atom.radius + 1.75} fill="#1a1a1a" />
            <Circle cx={atom.x} cy={atom.y} r={atom.radius} fill={atomColor(atom.element)} />
            {showsAtomLabel(style) ? (
              <SvgText
                x={atom.x}
                y={atom.y + 4}
                fill={atomLabelColor(atom.element)}
                fontFamily={CODE_FONT}
                fontSize={12}
                textAnchor="middle"
              >
                {atom.element}
              </SvgText>
            ) : null}
          </G>
        );
      })}
    </Svg>
  );
}

function MoleculeCanvas(props: MoleculeCanvasProps) {
  if (!isSkiaAvailable()) return <SvgMoleculeCanvas {...props} />;
  return (
    <Suspense fallback={<SvgMoleculeCanvas {...props} />}>
      <SkiaMoleculeCanvasLazy {...props} />
    </Suspense>
  );
}

/** 3D canvas + style picker without card chrome — used by Molecule3DBlock and MoleculeCard. */
export function Molecule3DView({ geom }: { geom: MolGeometry }) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [style, setStyle] = useState<MoleculeStyle>("ball-stick");
  const [canvasWidth, setCanvasWidth] = useState(320);
  const [yaw, setYaw] = useState(0.7);
  const [pitch, setPitch] = useState(0.35);
  const yawRef = useRef(0.7);
  const pitchRef = useRef(0.35);
  const startYaw = useRef(0.7);
  const startPitch = useRef(0.35);
  yawRef.current = yaw;
  pitchRef.current = pitch;

  const pan = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_e, g) => Math.abs(g.dx) > 3 || Math.abs(g.dy) > 3,
        onPanResponderGrant: () => {
          startYaw.current = yawRef.current;
          startPitch.current = pitchRef.current;
        },
        onPanResponderMove: (_e, g) => {
          setYaw(startYaw.current + g.dx * 0.012);
          setPitch(Math.max(-1.2, Math.min(1.2, startPitch.current + g.dy * 0.012)));
        },
      }),
    [],
  );

  const styles = useMemo(
    () => [
      { key: "ball-stick" as const, label: t("rich.chemistry_style_ball") },
      { key: "spacefill" as const, label: t("rich.chemistry_style_sphere") },
      { key: "wireframe" as const, label: t("rich.chemistry_style_wire") },
    ],
    [t],
  );

  return (
    <>
      <View
        style={s.stage}
        onLayout={(event) => setCanvasWidth(Math.max(1, event.nativeEvent.layout.width))}
        {...pan.panHandlers}
      >
        <MoleculeCanvas
          geom={geom}
          style={style}
          theme={theme}
          yaw={yaw}
          pitch={pitch}
          width={canvasWidth}
        />
      </View>
      <View style={s.styleRow}>
        <SegmentedControl
          segments={styles}
          value={style}
          onChange={setStyle}
          accessibilityLabel={t("rich.chemistry_style_a11y")}
          testID="molecule-style"
        />
      </View>
    </>
  );
}

export function Molecule3DBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);

  const parsed = useMemo(() => parseMolecule3DFence(content), [content]);
  const sdf = parsed?.sdf ?? "";
  const caption = parsed?.caption;
  const geom = useMemo(() => (sdf ? parseMolGeometry(sdf) : null), [sdf]);

  if (!parsed || !geom) {
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
      actions={
        <>
          <View style={s.spacer} />
          <CopyButton text={sdf} accessibilityLabel={t("rich.chemistry_copy_structure")} />
        </>
      }
    >
      {caption ? <MoleculeCaption text={caption} /> : null}

      <Molecule3DView geom={geom} />
    </VisualCard>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    stage: {
      height: MOLECULE_PREVIEW_HEIGHT,
      backgroundColor: t.contentSurface,
    },
    spacer: { flex: 1 },
    styleRow: {
      paddingHorizontal: Space.sm + 2,
      paddingTop: Space.xs + 2,
    },
  });
}
