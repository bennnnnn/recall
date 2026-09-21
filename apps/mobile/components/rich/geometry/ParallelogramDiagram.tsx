import Svg, { Line, Polygon, Text as SvgText } from "react-native-svg";

import { InteriorAngleMarks } from "@/components/rich/geometry/GeometryMarks";
import {
  computeParallelogramLabels,
  geometryLabelInset,
  padDiagramForAngleLabels,
  parallelogramLayout,
  type ParallelogramSpec,
} from "@/lib/math/geometryBlock";
import i18n from "@/lib/i18n";
import { type Theme } from "@/lib/theme";

export function ParallelogramDiagram({
  spec,
  screenWidth,
  theme,
}: {
  spec: ParallelogramSpec;
  screenWidth: number;
  theme: Theme;
}) {
  const labels = computeParallelogramLabels(spec);
  const padding =
    spec.show_labels !== false
      ? {
          left: geometryLabelInset(labels.height, 12),
          right: geometryLabelInset(labels.side, 12),
        }
      : { left: 40, right: 40 };
  const { svgW, svgH, bx0, bx1, by, tx0, tx1, ty } = parallelogramLayout(
    spec,
    screenWidth,
    padding,
  );
  const showLabels = spec.show_labels !== false;
  const showAngle = spec.show_angle === true;
  let verts = [
    { x: tx0, y: ty },
    { x: tx1, y: ty },
    { x: bx1, y: by },
    { x: bx0, y: by },
  ];
  let outW = svgW;
  let outH = svgH;
  if (showAngle) {
    const padded = padDiagramForAngleLabels(verts, svgW, svgH);
    verts = padded.vertices;
    outW = padded.svgW;
    outH = padded.svgH;
  }
  const [tl, tr, br, bl] = verts;

  return (
    <Svg width={outW} height={outH}>
      <Polygon
        points={`${tl.x},${tl.y} ${tr.x},${tr.y} ${br.x},${br.y} ${bl.x},${bl.y}`}
        fill={theme.contentSurface}
        stroke={theme.primary}
        strokeWidth={2}
      />
      <Line
        x1={tl.x}
        y1={tl.y}
        x2={tl.x}
        y2={bl.y}
        stroke={theme.accent}
        strokeWidth={2}
        strokeDasharray="5,4"
      />
      {showAngle ? (
        <InteriorAngleMarks
          vertices={verts}
          color={theme.textSecondary}
          fill={theme.contentSurface}
        />
      ) : null}
      {showLabels ? (
        <>
          <SvgText
            x={(tl.x + tr.x) / 2}
            y={tl.y - 8}
            fill={theme.text}
            fontSize={13}
            fontWeight="600"
            textAnchor="middle"
          >
            {labels.base}
          </SvgText>
          <SvgText
            x={(bl.x + br.x) / 2}
            y={bl.y + 18}
            fill={theme.text}
            fontSize={13}
            fontWeight="600"
            textAnchor="middle"
          >
            {labels.base}
          </SvgText>
          <SvgText
            x={tl.x - 8}
            y={(tl.y + bl.y) / 2}
            fill={theme.accent}
            fontSize={12}
            fontWeight="600"
            textAnchor="end"
          >
            {labels.height}
          </SvgText>
          <SvgText
            x={(tl.x + bl.x) / 2 - 8}
            y={(tl.y + bl.y) / 2 - 10}
            fill={theme.text}
            fontSize={12}
            fontWeight="600"
            textAnchor="end"
          >
            {labels.side}
          </SvgText>
          <SvgText
            x={(tr.x + br.x) / 2 + 8}
            y={(tr.y + br.y) / 2 - 10}
            fill={theme.text}
            fontSize={12}
            fontWeight="600"
            textAnchor="start"
          >
            {labels.side}
          </SvgText>
          <SvgText
            x={(bl.x + br.x) / 2}
            y={bl.y + 40}
            fill={theme.textSecondary}
            fontSize={12}
            textAnchor="middle"
          >
            {spec.show_perimeter
              ? `${i18n.t("rich.perimeter")}\u00A0${labels.perimeter}`
              : `${i18n.t("rich.area")}\u00A0${labels.area}`}
          </SvgText>
        </>
      ) : null}
    </Svg>
  );
}
