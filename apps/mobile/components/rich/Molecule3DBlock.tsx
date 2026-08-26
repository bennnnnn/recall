/**
 * 3D molecule viewer — native SVG ball-and-stick from SDF coordinates.
 * WKWebView + 3Dmol.js WebGL stays blank (CSP / zero-size canvas), so we
 * project the same 3D coords that RDKit already computed.
 */
import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { PanResponder, Pressable, StyleSheet, Text, View } from "react-native";
import Svg, { Circle, Line, Text as SvgText } from "react-native-svg";
import { Icon } from "@/components/Icon";
import { CopyButton } from "@/components/CopyButton";
import {
  parseMolGeometry,
  parseMolecule3DFence,
  type MolAtom,
  type MolGeometry,
} from "@/lib/molecule3dFence";
import { Theme, useTheme } from "@/lib/theme";

type Props = { content: string };

const PREVIEW_HEIGHT = 280;
const VIEW_PAD = 36;

type MoleculeStyle = "ball-stick" | "spacefill" | "wireframe";

const CPK: Record<string, string> = {
  H: "#c5cdd8",
  C: "#3d3d3d",
  N: "#3b6bdb",
  O: "#e31c1c",
  F: "#3aaa3a",
  P: "#e07000",
  S: "#d4b41c",
  Cl: "#1f9a1f",
  Br: "#a62929",
  I: "#940094",
};

const LIGHT_ATOMS = new Set(["H", "F", "S", "Cl"]);

const RADIUS: Record<string, number> = {
  H: 0.32,
  C: 0.7,
  N: 0.65,
  O: 0.6,
  F: 0.5,
  P: 0.9,
  S: 0.88,
  Cl: 0.79,
  Br: 0.94,
  I: 1.15,
};

function atomColor(el: string): string {
  return CPK[el] ?? "#c45c9a";
}

function atomLabelColor(el: string): string {
  return LIGHT_ATOMS.has(el) ? "#1a1a1a" : "#fff";
}

function atomRadius(el: string): number {
  return RADIUS[el] ?? 0.7;
}

function project(atom: MolAtom, yaw: number, pitch: number) {
  const cy = Math.cos(yaw);
  const sy = Math.sin(yaw);
  const x1 = atom.x * cy + atom.z * sy;
  const z1 = -atom.x * sy + atom.z * cy;
  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);
  return { x: x1, y: atom.y * cp - z1 * sp, z: atom.y * sp + z1 * cp };
}

function layout(
  geom: MolGeometry,
  yaw: number,
  pitch: number,
  width: number,
  height: number,
  style: MoleculeStyle,
) {
  const atomScale = style === "spacefill" ? 0.72 : style === "wireframe" ? 0.2 : 0.32;
  const projected = geom.atoms.map((atom) => project(atom, yaw, pitch));
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (let i = 0; i < projected.length; i++) {
    const p = projected[i]!;
    const r = atomRadius(geom.atoms[i]!.el) * atomScale;
    if (p.x - r < minX) minX = p.x - r;
    if (p.x + r > maxX) maxX = p.x + r;
    if (p.y - r < minY) minY = p.y - r;
    if (p.y + r > maxY) maxY = p.y + r;
  }
  const span = Math.max(maxX - minX, maxY - minY, 0.8);
  const scale = (Math.min(width, height) - VIEW_PAD * 2) / span;
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const atoms = projected.map((p, i) => ({
    i,
    el: geom.atoms[i]!.el,
    x: (p.x - cx) * scale + width / 2,
    y: (cy - p.y) * scale + height / 2,
    z: p.z,
    r: Math.max(3, atomRadius(geom.atoms[i]!.el) * scale * atomScale),
  }));
  const order = atoms.map((_, i) => i).sort((a, b) => atoms[a]!.z - atoms[b]!.z);
  return { atoms, order, scale };
}

function bondOffset(dx: number, dy: number, dist: number, mag: number) {
  return { x: (-dy / dist) * mag, y: (dx / dist) * mag };
}

function MoleculeSvg({
  geom,
  style,
  theme,
  yaw,
  pitch,
}: {
  geom: MolGeometry;
  style: MoleculeStyle;
  theme: Theme;
  yaw: number;
  pitch: number;
}) {
  const width = 320;
  const height = PREVIEW_HEIGHT;
  const laid = layout(geom, yaw, pitch, width, height, style);
  const showBonds = style !== "spacefill";
  const bondW = style === "wireframe" ? 1.6 : 3.4;

  return (
    <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`}>
      {showBonds
        ? geom.bonds.map((bond, bi) => {
            const a = laid.atoms[bond.a]!;
            const b = laid.atoms[bond.b]!;
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const dist = Math.hypot(dx, dy) || 1;
            const copies = Math.min(3, Math.max(1, bond.order));
            const spread = copies === 1 ? 0 : copies === 2 ? 3.2 : 4.2;
            const lines = [];
            for (let k = 0; k < copies; k++) {
              const t = copies === 1 ? 0 : (k - (copies - 1) / 2) * spread;
              const o = bondOffset(dx, dy, dist, t);
              lines.push(
                <Line
                  key={`${bi}-${k}`}
                  x1={a.x + o.x}
                  y1={a.y + o.y}
                  x2={b.x + o.x}
                  y2={b.y + o.y}
                  stroke={theme.text}
                  strokeWidth={bondW}
                  strokeLinecap="round"
                />,
              );
            }
            return lines;
          })
        : null}
      {laid.order.map((idx) => {
        const atom = laid.atoms[idx]!;
        const fill = atomColor(atom.el);
        return (
          <Circle
            key={`a-${idx}`}
            cx={atom.x}
            cy={atom.y}
            r={atom.r}
            fill={fill}
            stroke="#1a1a1a"
            strokeWidth={1.75}
          />
        );
      })}
      {style !== "spacefill"
        ? laid.order.map((idx) => {
            const atom = laid.atoms[idx]!;
            if (atom.r < 8) return null;
            return (
              <SvgText
                key={`t-${idx}`}
                x={atom.x}
                y={atom.y + 4}
                fontSize={Math.min(14, atom.r)}
                fontWeight="700"
                fill={atomLabelColor(atom.el)}
                textAnchor="middle"
              >
                {atom.el}
              </SvgText>
            );
          })
        : null}
    </Svg>
  );
}

export function Molecule3DBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [style, setStyle] = useState<MoleculeStyle>("ball-stick");
  const [yaw, setYaw] = useState(0.7);
  const [pitch, setPitch] = useState(0.35);
  const yawRef = useRef(0.7);
  const pitchRef = useRef(0.35);
  const startYaw = useRef(0.7);
  const startPitch = useRef(0.35);
  yawRef.current = yaw;
  pitchRef.current = pitch;

  const parsed = useMemo(() => parseMolecule3DFence(content), [content]);
  const sdf = parsed?.sdf ?? "";
  const caption = parsed?.caption;
  const geom = useMemo(() => (sdf ? parseMolGeometry(sdf) : null), [sdf]);

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

  if (!parsed || !geom) {
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

      <View style={s.stage} {...pan.panHandlers}>
        <MoleculeSvg geom={geom} style={style} theme={theme} yaw={yaw} pitch={pitch} />
      </View>

      <View style={s.actions}>
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
        <CopyButton text={sdf} />
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
    stage: { height: PREVIEW_HEIGHT, backgroundColor: t.contentSurface },
    previewBox: {
      paddingHorizontal: 14,
      paddingVertical: 24,
      backgroundColor: t.contentSurface,
      alignItems: "center",
    },
    fallbackHint: { fontSize: 13, color: t.textTertiary, textAlign: "center" },
    actions: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 10,
      paddingHorizontal: 14,
      paddingVertical: 10,
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
