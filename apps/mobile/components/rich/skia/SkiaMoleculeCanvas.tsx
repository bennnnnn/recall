import { useMemo } from "react";
import {
  Canvas,
  Circle,
  Path,
  Skia,
  Text as SkiaText,
  useFont,
} from "@shopify/react-native-skia";

import {
  atomColor,
  atomLabelColor,
  bondOffset,
  layoutMolecule,
  MOLECULE_PREVIEW_HEIGHT,
  type MoleculeStyle,
} from "@/components/rich/molecule3dLayout";
import type { MolGeometry } from "@/lib/chemistry/molecule3dFence";
import type { Theme } from "@/lib/theme";

type Props = {
  geom: MolGeometry;
  style: MoleculeStyle;
  theme: Theme;
  yaw: number;
  pitch: number;
  width: number;
};

function linePath(x1: number, y1: number, x2: number, y2: number) {
  const path = Skia.Path.Make();
  path.moveTo(x1, y1);
  path.lineTo(x2, y2);
  return path;
}

export function SkiaMoleculeCanvas({
  geom,
  style,
  theme,
  yaw,
  pitch,
  width,
}: Props) {
  const height = MOLECULE_PREVIEW_HEIGHT;
  const font = useFont(require("../../../assets/fonts/SpaceMono-Regular.ttf"), 12);
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
          path: linePath(
            first.x + offset.x,
            first.y + offset.y,
            second.x + offset.x,
            second.y + offset.y,
          ),
        };
      });
    });
  }, [geom.bonds, laidOut.atoms, showBonds]);

  return (
    <Canvas testID="molecule-skia-canvas" style={{ width, height }}>
      {bonds.map((bond) => (
        <Path
          key={bond.key}
          path={bond.path}
          color={theme.text}
          style="stroke"
          strokeWidth={bondWidth}
          strokeCap="round"
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
            color="#1a1a1a"
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
            color={atomColor(atom.element)}
          />
        );
      })}
      {style !== "spacefill"
        ? laidOut.depthOrder.map((index) => {
            const atom = laidOut.atoms[index]!;
            if (atom.radius < 8 || !font) return null;
            const measured = font.measureText(atom.element);
            return (
              <SkiaText
                key={`label-${index}`}
                x={atom.x - measured.width / 2}
                y={atom.y + 4}
                text={atom.element}
                font={font}
                color={atomLabelColor(atom.element)}
              />
            );
          })
        : null}
    </Canvas>
  );
}
