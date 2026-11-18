/**
 * An electric field diagram: the field lines exactly as the server traced
 * them, one arrowhead on each, the charges or plates they run between, and the
 * neutral points. The phone works out no field (`lib/physics/field.ts`).
 */
import { useMemo } from "react";
import { useWindowDimensions } from "react-native";
import { useTranslation } from "react-i18next";
import { Group, Path, Skia, type SkPath } from "@shopify/react-native-skia";

import { figureWidth } from "@/components/rich/figure";
import { appendArrowHead, pointsPath, segmentsPath } from "@/components/rich/skia/paths";
import { HaloText } from "@/components/rich/skia/HaloText";
import {
  DiagramFrame,
  useDiagramFont,
  useDiagramTitle,
} from "@/components/rich/diagrams/DiagramFrame";
import type { FieldDiagramSpec } from "@/components/rich/diagrams/spec";
import { DIAGRAM_FONT_SIZE, measureDiagramText } from "@/components/rich/diagrams/textWidth";
import { fieldTitle, layoutFieldScene, type FieldScene } from "@/lib/physics/field";
import { worldViewportHeight } from "@/lib/physics/optics";
import { useTheme } from "@/lib/theme";

const LINE_STROKE = 1.5;
const HEAD = 7;
const PLATE_STROKE = 5;
const SIGN_STROKE = 2;
/** The + or − inside a charge, as a share of its radius. */
const SIGN_SIZE = 0.5;
const PLATE_SIGN = 4;
const PLATE_SIGN_OFFSET = 10;
const NEUTRAL_MARK = 5;
const LABEL_GAP = 4;

type Ends = { x1: number; y1: number; x2: number; y2: number };

/** A plus or a minus centred on (x, y), `size` from the centre to each end. */
function signStrokes(x: number, y: number, size: number, sign: 1 | -1): Ends[] {
  const across = { x1: x - size, y1: y, x2: x + size, y2: y };
  return sign > 0 ? [across, { x1: x, y1: y - size, x2: x, y2: y + size }] : [across];
}

function scenePaths(scene: FieldScene) {
  const heads = Skia.PathBuilder.Make();
  for (const arrow of scene.arrows) {
    appendArrowHead(heads, arrow.tip.px, arrow.tip.py, arrow.ux, arrow.uy, HEAD, "filled");
  }
  const discs = (sign: 1 | -1): SkPath => {
    const path = Skia.PathBuilder.Make();
    for (const charge of scene.charges) {
      if (charge.sign === sign) path.addCircle(charge.centre.px, charge.centre.py, charge.r);
    }
    return path.detach();
  };
  const signs = scene.charges.flatMap((charge) =>
    signStrokes(charge.centre.px, charge.centre.py, charge.r * SIGN_SIZE, charge.sign),
  );
  // Each plate's signs sit on its outer side, clear of the lines between the plates.
  const plateSigns = scene.plates.flatMap((plate) => {
    const away = outward(scene, plate) * PLATE_SIGN_OFFSET;
    return plate.marks.flatMap((mark) => signStrokes(mark.px, mark.py + away, PLATE_SIGN, plate.sign));
  });
  return {
    lines: scene.lines.map((line) => pointsPath(line)),
    heads: heads.detach(),
    positive: discs(1),
    negative: discs(-1),
    signs: segmentsPath(signs),
    plates: scene.plates.map((plate) => ({
      sign: plate.sign,
      path: segmentsPath([{ x1: plate.from.px, y1: plate.from.py, x2: plate.to.px, y2: plate.to.py }]),
    })),
    plateSigns: segmentsPath(plateSigns),
    neutral: segmentsPath(
      scene.neutral.flatMap((point) => [
        { x1: point.px - NEUTRAL_MARK, y1: point.py - NEUTRAL_MARK, x2: point.px + NEUTRAL_MARK, y2: point.py + NEUTRAL_MARK },
        { x1: point.px - NEUTRAL_MARK, y1: point.py + NEUTRAL_MARK, x2: point.px + NEUTRAL_MARK, y2: point.py - NEUTRAL_MARK },
      ]),
    ),
  };
}

/** Which way is away from the other plate, on screen: -1 up, 1 down. */
function outward(scene: FieldScene, plate: FieldScene["plates"][number]): number {
  const others = scene.plates.filter((other) => other !== plate);
  if (!others.length) return -1;
  return plate.from.py < others[0].from.py ? -1 : 1;
}

export function FieldDiagram({ spec }: { spec: FieldDiagramSpec }) {
  const theme = useTheme();
  const { t } = useTranslation();
  const { width: screenWidth } = useWindowDimensions();
  const width = figureWidth(screenWidth);
  const font = useDiagramFont();
  const title = fieldTitle(useDiagramTitle(spec), spec.field.part);
  const height = useMemo(() => worldViewportHeight(spec.bounds, width), [spec, width]);
  const scene = useMemo(() => layoutFieldScene(spec.field, spec.bounds, width, height), [height, spec, width]);
  const paths = useMemo(() => scenePaths(scene), [scene]);
  const description = spec.alt ?? title;
  const neutralText = t("rich.diagram_mark_neutral");

  const markers = useMemo(
    () => [
      ...spec.field.lines.map(() => "field-line"),
      ...spec.field.arrows.map(() => "field-arrow"),
      ...spec.field.charges.map((charge) => (charge.sign > 0 ? "field-charge-positive" : "field-charge-negative")),
      ...spec.field.plates.map((plate) => (plate.sign > 0 ? "field-plate-positive" : "field-plate-negative")),
      ...spec.field.neutral.map(() => "field-neutral"),
    ],
    [spec],
  );

  const lineColor = theme.textSecondary;
  const positive = theme.danger;
  const negative = theme.primary;
  return (
    <DiagramFrame
      testID="field-canvas"
      title={title}
      description={description}
      width={width}
      height={height}
      markers={markers}
    >
      <Group clip={Skia.XYWHRect(0, 0, width, height)}>
        {paths.lines.map((line, index) => (
          <Path
            key={`line-${index}`}
            path={line}
            color={lineColor}
            style="stroke"
            strokeWidth={LINE_STROKE}
            strokeJoin="round"
            strokeCap="round"
          />
        ))}
        <Path path={paths.heads} color={lineColor} style="fill" />
        {paths.plates.map((plate, index) => (
          <Path
            key={`plate-${index}`}
            path={plate.path}
            color={plate.sign > 0 ? positive : negative}
            style="stroke"
            strokeWidth={PLATE_STROKE}
            strokeCap="round"
          />
        ))}
        <Path path={paths.plateSigns} color={theme.text} style="stroke" strokeWidth={1.5} strokeCap="round" />
        <Path path={paths.positive} color={positive} style="fill" />
        <Path path={paths.negative} color={negative} style="fill" />
        <Path path={paths.signs} color={theme.bg} style="stroke" strokeWidth={SIGN_STROKE} strokeCap="round" />
        <Path path={paths.neutral} color={theme.text} style="stroke" strokeWidth={1.5} strokeCap="round" />
      </Group>
      {font ? (
        <>
          {scene.charges.map((charge, index) =>
            charge.label ? (
              <HaloText
                key={`charge-label-${index}`}
                x={charge.centre.px - measureDiagramText(charge.label) / 2}
                y={charge.centre.py + charge.r + LABEL_GAP + DIAGRAM_FONT_SIZE}
                text={charge.label}
                font={font}
                color={theme.text}
                halo={theme.bg}
              />
            ) : null,
          )}
          {scene.neutral.map((point, index) => (
            <HaloText
              key={`neutral-label-${index}`}
              x={point.px - measureDiagramText(neutralText) / 2}
              y={point.py + NEUTRAL_MARK + LABEL_GAP + DIAGRAM_FONT_SIZE}
              text={neutralText}
              font={font}
              color={theme.textSecondary}
              halo={theme.bg}
            />
          ))}
        </>
      ) : null}
    </DiagramFrame>
  );
}
