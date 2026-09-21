/**
 * 3D molecule viewer — native-first Skia ball-and-stick from SDF coordinates.
 * WKWebView + 3Dmol.js WebGL stays blank (CSP / zero-size canvas), so we
 * project the same 3D coords that RDKit already computed. Expo Go and stale
 * native clients safely use the matching SVG renderer.
 */
import { lazy, Suspense, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { PanResponder, Pressable, StyleSheet, Text, View } from "react-native";
import Svg, { Circle, Line, Text as SvgText } from "react-native-svg";

import { CopyButton } from "@/components/CopyButton";
import {
  atomColor,
  atomLabelColor,
  bondOffset,
  layoutMolecule,
  MOLECULE_PREVIEW_HEIGHT,
  type MoleculeStyle,
} from "@/components/rich/molecule3dLayout";
import { VisualCard } from "@/components/rich/VisualCard";
import {
  parseMolGeometry,
  parseMolecule3DFence,
  type MolGeometry,
} from "@/lib/chemistry/molecule3dFence";
import { isSkiaAvailable } from "@/lib/skiaAvailability";
import { Theme, useTheme } from "@/lib/theme";

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

function SvgMoleculeCanvas({
  geom,
  style,
  theme,
  yaw,
  pitch,
  width,
}: MoleculeCanvasProps) {
  const height = MOLECULE_PREVIEW_HEIGHT;
  const laidOut = useMemo(
    () => layoutMolecule(geom, yaw, pitch, width, height, style),
    [geom, height, pitch, style, width, yaw],
  );
  const showBonds = style !== "spacefill";
  const bondWidth = style === "wireframe" ? 1.6 : 3.4;
  const bonds = useMemo(() => {
    if (!showBonds) return [];
    return geom.bonds.flatMap((bond, bondIndex) => {
      const first = laidOut.atoms[bond.a]!;
      const second = laidOut.atoms[bond.b]!;
      const dx = second.x - first.x;
      const dy = second.y - first.y;
      const distance = Math.hypot(dx, dy) || 1;
      const copies = Math.min(3, Math.max(1, bond.order));
      const spread = copies === 1 ? 0 : copies === 2 ? 3.2 : 4.2;
      return Array.from({ length: copies }, (_, copyIndex) => {
        const offsetIndex =
          copies === 1 ? 0 : (copyIndex - (copies - 1) / 2) * spread;
        const offset = bondOffset(dx, dy, distance, offsetIndex);
        return {
          key: `${bondIndex}-${copyIndex}`,
          x1: first.x + offset.x,
          y1: first.y + offset.y,
          x2: second.x + offset.x,
          y2: second.y + offset.y,
        };
      });
    });
  }, [geom.bonds, laidOut.atoms, showBonds]);

  return (
    <Svg
      testID="molecule-svg-fallback"
      width={width}
      height={height}
      accessibilityLabel="Interactive 3D molecule"
    >
      {bonds.map((bond) => (
        <Line
          key={bond.key}
          x1={bond.x1}
          y1={bond.y1}
          x2={bond.x2}
          y2={bond.y2}
          stroke={theme.text}
          strokeWidth={bondWidth}
          strokeLinecap="round"
        />
      ))}
      {laidOut.depthOrder.map((index) => {
        const atom = laidOut.atoms[index]!;
        return (
          <Circle
            key={`outline-${index}`}
            cx={atom.x}
            cy={atom.y}
            r={atom.radius + 1.75}
            fill="#1a1a1a"
          />
        );
      })}
      {laidOut.depthOrder.map((index) => {
        const atom = laidOut.atoms[index]!;
        return (
          <Circle
            key={`atom-${index}`}
            cx={atom.x}
            cy={atom.y}
            r={atom.radius}
            fill={atomColor(atom.element)}
          />
        );
      })}
      {style !== "spacefill"
        ? laidOut.depthOrder.map((index) => {
            const atom = laidOut.atoms[index]!;
            if (atom.radius < 8) return null;
            return (
              <SvgText
                key={`label-${index}`}
                x={atom.x}
                y={atom.y + 4}
                fill={atomLabelColor(atom.element)}
                fontFamily="SpaceMono-Regular"
                fontSize={12}
                textAnchor="middle"
              >
                {atom.element}
              </SvgText>
            );
          })
        : null}
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

/** 3D canvas + style chips without card chrome — used by Molecule3DBlock and MoleculeCard. */
export function Molecule3DView({ sdf }: { sdf: string }) {
  const theme = useTheme();
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

  const geom = useMemo(() => parseMolGeometry(sdf), [sdf]);

  const pan = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_e, g) =>
          Math.abs(g.dx) > 3 || Math.abs(g.dy) > 3,
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

  if (!geom) return null;

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
      <View style={s.styleRowWrap}>
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
      <VisualCard label={t("rich.chemistry_structure")} icon="flask-outline">
        <View style={s.previewBox}>
          <Text style={s.fallbackHint}>{t("rich.chemistry_invalid")}</Text>
        </View>
      </VisualCard>
    );
  }

  return (
    <VisualCard
      label={t("rich.chemistry_structure")}
      icon="flask-outline"
      actions={
        <>
          <View style={s.spacer} />
          <CopyButton text={sdf} />
        </>
      }
    >
      {caption ? (
        <View style={s.captionBox}>
          <Text style={s.captionText}>{caption}</Text>
        </View>
      ) : null}

      <Molecule3DView sdf={sdf} />
    </VisualCard>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    captionBox: {
      paddingHorizontal: 14,
      paddingTop: 8,
      paddingBottom: 0,
      backgroundColor: t.bg,
    },
    captionText: { fontSize: 13, fontWeight: "600", color: t.textSecondary },
    stage: {
      height: MOLECULE_PREVIEW_HEIGHT,
      backgroundColor: t.contentSurface,
    },
    previewBox: {
      paddingHorizontal: 14,
      paddingVertical: 24,
      backgroundColor: t.contentSurface,
      alignItems: "center",
    },
    fallbackHint: { fontSize: 13, color: t.textTertiary, textAlign: "center" },
    spacer: { flex: 1 },
    styleRowWrap: {
      paddingHorizontal: 14,
      paddingTop: 10,
    },
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
    styleBtnTextActive: { color: t.onPrimary },
  });
}
