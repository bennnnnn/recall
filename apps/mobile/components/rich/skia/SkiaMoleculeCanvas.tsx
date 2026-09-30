import { useMemo } from "react";
import {
  Canvas,
  Circle,
  Group,
  Path,
  Skia,
  Text as SkiaText,
  useFont,
} from "@shopify/react-native-skia";

import {
  atomColor,
  atomLabelColor,
  bondStrokeWidth,
  layoutMolecule,
  MOLECULE_PREVIEW_HEIGHT,
  type MoleculeStyle,
} from "@/lib/chemistry/molecule3dLayout";
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

export function SkiaMoleculeCanvas({ geom, style, theme, yaw, pitch, width }: Props) {
  const height = MOLECULE_PREVIEW_HEIGHT;
  const font = useFont(require("../../../assets/fonts/SpaceMono-Regular.ttf"), 12);
  const laidOut = useMemo(
    () => layoutMolecule(geom, yaw, pitch, width, height, style),
    [geom, height, pitch, style, width, yaw],
  );
  const paths = useMemo(
    () => laidOut.bonds.map((bond) => linePath(bond.x1, bond.y1, bond.x2, bond.y2)),
    [laidOut.bonds],
  );

  return (
    <Canvas testID="molecule-skia-canvas" style={{ width, height }}>
      {laidOut.drawOrder.map((item) => {
        if (item.kind === "bond") {
          return (
            <Path
              key={`bond-${laidOut.bonds[item.index]!.key}`}
              path={paths[item.index]!}
              color={theme.text}
              style="stroke"
              strokeWidth={bondStrokeWidth(style)}
              strokeCap="round"
            />
          );
        }
        const atom = laidOut.atoms[item.index]!;
        return (
          <Group key={`atom-${atom.index}`}>
            <Circle cx={atom.x} cy={atom.y} r={atom.radius + 1.75} color="#1a1a1a" />
            <Circle cx={atom.x} cy={atom.y} r={atom.radius} color={atomColor(atom.element)} />
            {style !== "spacefill" && atom.radius >= 8 && font ? (
              <SkiaText
                x={atom.x - font.measureText(atom.element).width / 2}
                y={atom.y + 4}
                text={atom.element}
                font={font}
                color={atomLabelColor(atom.element)}
              />
            ) : null}
          </Group>
        );
      })}
    </Canvas>
  );
}
