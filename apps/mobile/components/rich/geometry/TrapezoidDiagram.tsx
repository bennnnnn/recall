import Svg, { Line, Polygon, Text as SvgText } from "react-native-svg";

import { InteriorAngleMarks } from "@/components/rich/geometry/GeometryMarks";
import {
  computeTrapezoidLabels,
  geometryLabelInset,
  padDiagramForAngleLabels,
  type TrapezoidSpec,
} from "@/lib/math/geometryBlock";
import i18n from "@/lib/i18n";
import { type Theme } from "@/lib/theme";

export function TrapezoidDiagram({
  spec,
  screenWidth,
  theme,
}: {
  spec: TrapezoidSpec;
  screenWidth: number;
  theme: Theme;
}) {
  const labels = computeTrapezoidLabels(spec);
  const offsetX = spec.show_labels !== false ? geometryLabelInset(labels.height, 12) : 40;
  const rightPad = 40;
  const inner = Math.max(screenWidth - 48 - offsetX - rightPad, 1);
  const scale = inner / Math.max(spec.top, spec.bottom, spec.height, 1);
  const topW = spec.top * scale;
  const bottomW = spec.bottom * scale;
  const h = spec.height * scale;
  const offsetY = 28;
  const bx0 = offsetX;
  const bx1 = offsetX + bottomW;
  const by = offsetY + h;
  const tx0 = offsetX + (bottomW - topW) / 2;
  const tx1 = tx0 + topW;
  const ty = offsetY;
  const svgW = bottomW + offsetX + rightPad;
  const svgH = h + offsetY + 40;
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
      <Line x1={tl.x} y1={tl.y} x2={tl.x} y2={bl.y} stroke={theme.accent} strokeWidth={2} strokeDasharray="5,4" />
      {showAngle ? (
        <InteriorAngleMarks vertices={verts} color={theme.textSecondary} fill={theme.contentSurface} />
      ) : null}
      {showLabels ? (
        <>
          <SvgText x={(tl.x + tr.x) / 2} y={tl.y - 8} fill={theme.text} fontSize={13} fontWeight="600" textAnchor="middle">
            {labels.top}
          </SvgText>
          <SvgText x={(bl.x + br.x) / 2} y={bl.y + 18} fill={theme.text} fontSize={13} fontWeight="600" textAnchor="middle">
            {labels.bottom}
          </SvgText>
          <SvgText x={tl.x - 8} y={(tl.y + bl.y) / 2} fill={theme.accent} fontSize={12} fontWeight="600" textAnchor="end">
            {labels.height}
          </SvgText>
          <SvgText x={(bl.x + br.x) / 2} y={bl.y + 34} fill={theme.textSecondary} fontSize={12} textAnchor="middle">
            {`${i18n.t("rich.area")}\u00A0${labels.area}`}
          </SvgText>
        </>
      ) : null}
    </Svg>
  );
}
