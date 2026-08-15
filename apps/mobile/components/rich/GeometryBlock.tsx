import { useMemo } from "react";
import { StyleSheet, Text, useWindowDimensions, View } from "react-native";
import Svg, { Circle, Line, Path, Polygon, Rect, Text as SvgText } from "react-native-svg";

import {
  computeCircleLabels,
  computeParallelogramLabels,
  computeRectangleLabels,
  computeRightTriangleLabels,
  computeSectorLabels,
  computeTrapezoidLabels,
  computeTriangleLabels,
  computeTriangleSidesLabels,
  diagonalAngleArcPath,
  equalSideTickCounts,
  footOfPerpendicular,
  isIsoscelesSides,
  isRightAngleDeg,
  midpoint,
  parseGeometrySpec,
  parallelogramLayout,
  polygonInteriorAngleMarks,
  padDiagramForAngleLabels,
  rectangleAngleDisplay,
  scaleToFit,
  shouldShowTicks,
  sideTickMarks,
  triangleSidesVertices,
  baseHeightTriangleVertices,
  type CircleSpec,
  type ParallelogramSpec,
  type RectangleSpec,
  type RightTriangleSpec,
  type SectorSpec,
  type TickSegment,
  type TrapezoidSpec,
  type TriangleSidesSpec,
  type TriangleSpec,
  type VertexAngleMark,
} from "@/lib/geometryBlock";
import i18n from "@/lib/i18n";
import { Theme, useTheme } from "@/lib/theme";

type Props = { content: string };

function diagramColors(theme: Theme) {
  return {
    diagonal: theme.danger,
    height: theme.accent,
    hypotenuse: theme.danger,
    median: theme.textSecondary,
  };
}

function TickMarks({
  segments,
  color,
}: {
  segments: TickSegment[];
  color: string;
}) {
  return (
    <>
      {segments.map((seg, i) => (
        <Line
          key={`tick-${i}-${seg.x1}-${seg.y1}`}
          x1={seg.x1}
          y1={seg.y1}
          x2={seg.x2}
          y2={seg.y2}
          stroke={color}
          strokeWidth={1.5}
          accessibilityLabel="side-tick-mark"
        />
      ))}
    </>
  );
}

function InteriorAngleMarks({
  vertices,
  color,
  fill,
}: {
  vertices: { x: number; y: number }[];
  color: string;
  fill: string;
}) {
  const n = vertices.length;
  const marks = polygonInteriorAngleMarks(vertices);
  return (
    <>
      {marks.map((mark, i) => {
        const b = vertices[i];
        const a = vertices[(i + n - 1) % n];
        const c = vertices[(i + 1) % n];
        return (
          <VertexAngleGraphic
            key={`ang-${i}-${mark.text}`}
            mark={mark}
            a={a}
            b={b}
            c={c}
            color={color}
            fill={fill}
          />
        );
      })}
    </>
  );
}

function VertexAngleGraphic({
  mark,
  a,
  b,
  c,
  color,
  fill,
}: {
  mark: VertexAngleMark;
  a: { x: number; y: number };
  b: { x: number; y: number };
  c: { x: number; y: number };
  color: string;
  fill: string;
}) {
  const right = isRightAngleDeg(mark.deg);
  const size = 14;
  const la = Math.hypot(a.x - b.x, a.y - b.y) || 1;
  const lc = Math.hypot(c.x - b.x, c.y - b.y) || 1;
  const ux = ((a.x - b.x) / la) * size;
  const uy = ((a.y - b.y) / la) * size;
  const vx = ((c.x - b.x) / lc) * size;
  const vy = ((c.y - b.y) / lc) * size;
  return (
    <>
      {right ? (
        <Polygon
          points={`${b.x},${b.y} ${b.x + ux},${b.y + uy} ${b.x + ux + vx},${b.y + uy + vy} ${b.x + vx},${b.y + vy}`}
          fill="none"
          stroke={color}
          strokeWidth={1.5}
          accessibilityLabel="right-angle-mark"
        />
      ) : (
        <Path
          d={mark.path}
          fill="none"
          stroke={color}
          strokeWidth={1.5}
          accessibilityLabel="interior-angle-arc"
        />
      )}
      {mark.leader ? (
        <Line
          x1={mark.leader.x1}
          y1={mark.leader.y1}
          x2={mark.leader.x2}
          y2={mark.leader.y2}
          stroke={color}
          strokeWidth={1}
          accessibilityLabel="interior-angle-leader"
        />
      ) : null}
      <Rect
        x={mark.labelX - mark.labelWidth / 2}
        y={mark.labelY - mark.labelHeight / 2}
        width={mark.labelWidth}
        height={mark.labelHeight}
        rx={3}
        fill={fill}
        accessibilityLabel="interior-angle-backdrop"
      />
      <SvgText
        x={mark.labelX}
        y={mark.labelY}
        fill={color}
        fontSize={11}
        fontWeight="600"
        textAnchor="middle"
        alignmentBaseline="middle"
        accessibilityLabel={`interior-angle-${mark.text}`}
      >
        {mark.text}
      </SvgText>
    </>
  );
}

function RectangleDiagram({ spec, screenWidth, theme }: { spec: RectangleSpec; screenWidth: number; theme: Theme }) {
  const colors = diagramColors(theme);
  const labels = computeRectangleLabels(spec);
  const layout = scaleToFit(spec.width, spec.height, screenWidth - 48);
  const offsetX = 40;
  const offsetY = 36;
  const x = offsetX;
  const y = offsetY;
  const w = layout.w;
  const h = layout.h;
  const svgW = w + offsetX + 40;
  const svgH = h + offsetY + (spec.show_area || spec.show_perimeter ? 56 : 40);
  const isSquare = spec.type === "square";
  const corner = 12;
  const { showCornerBracket, showDiagonalAngleLabel } = rectangleAngleDisplay(spec);
  const showTicks = shouldShowTicks(spec.show_ticks, true);
  // Square: one tick on every side. Rectangle: 1 on the length pair, 2 on the width pair.
  const tickSegments = showTicks
    ? [
        ...sideTickMarks(x, y, x + w, y, 1),
        ...sideTickMarks(x, y + h, x + w, y + h, 1),
        ...sideTickMarks(x, y, x, y + h, isSquare ? 1 : 2),
        ...sideTickMarks(x + w, y, x + w, y + h, isSquare ? 1 : 2),
      ]
    : [];

  return (
    <Svg width={svgW} height={svgH}>
      <Rect
        x={x}
        y={y}
        width={w}
        height={h}
        fill={theme.contentSurface}
        stroke={theme.primary}
        strokeWidth={2}
        rx={isSquare ? 2 : 4}
      />
      {tickSegments.length > 0 ? <TickMarks segments={tickSegments} color={theme.textSecondary} /> : null}
      {showCornerBracket ? (
        <>
          <Polygon
            points={`${x},${y + h} ${x + corner},${y + h} ${x + corner},${y + h - corner} ${x},${y + h - corner}`}
            fill="none"
            stroke={theme.textSecondary}
            strokeWidth={1.5}
          />
          {isSquare ? (
            <Polygon
              points={`${x + w},${y + h} ${x + w - corner},${y + h} ${x + w - corner},${y + h - corner} ${x + w},${y + h - corner}`}
              fill="none"
              stroke={theme.textSecondary}
              strokeWidth={1.5}
            />
          ) : null}
        </>
      ) : null}
      {spec.show_diagonal ? (
        <Line
          x1={x}
          y1={y}
          x2={x + w}
          y2={y + h}
          stroke={colors.diagonal}
          strokeWidth={2}
          strokeDasharray="6,4"
        />
      ) : null}
      <SvgText x={x + w / 2} y={y - 10} fill={theme.text} fontSize={13} fontWeight="600" textAnchor="middle">
        {isSquare ? labels.side : labels.width}
      </SvgText>
      <SvgText x={x - 8} y={y + h / 2} fill={theme.text} fontSize={13} fontWeight="600" textAnchor="end">
        {isSquare ? labels.side : labels.height}
      </SvgText>
      {spec.show_diagonal ? (
        <SvgText x={x + w / 2 + 8} y={y + h / 2 - 6} fill={colors.diagonal} fontSize={12} fontWeight="600">
          {labels.diagonal}
        </SvgText>
      ) : null}
      {showDiagonalAngleLabel ? (
        // Diagonal-vs-base angle at the top-left (where TL→BR diagonal
        // meets the top edge) — NOT the rectangle's own 90° corner.
        // Arc + ∠ label; bracket is suppressed when the diagonal is drawn.
        <>
          <Path
            d={diagonalAngleArcPath(x, y, w, h)}
            fill="none"
            stroke={theme.textSecondary}
            strokeWidth={1.5}
            accessibilityLabel="diagonal-angle-arc"
          />
          <SvgText x={x + 22} y={y + 28} fill={theme.textSecondary} fontSize={12}>
            {`∠\u00A0${labels.angle}`}
          </SvgText>
        </>
      ) : null}
      {spec.show_area ? (
        <SvgText x={x + w / 2} y={y + h + 34} fill={theme.textSecondary} fontSize={12} textAnchor="middle">
          {`${i18n.t("rich.area")}\u00A0${labels.area}`}
        </SvgText>
      ) : null}
      {spec.show_perimeter ? (
        <SvgText x={x + w / 2} y={y + h + (spec.show_area ? 50 : 34)} fill={theme.textSecondary} fontSize={12} textAnchor="middle">
          {`${i18n.t("rich.perimeter")}\u00A0${labels.perimeter}`}
        </SvgText>
      ) : null}
    </Svg>
  );
}

function TriangleDiagram({ spec, screenWidth, theme }: { spec: TriangleSpec; screenWidth: number; theme: Theme }) {
  const colors = diagramColors(theme);
  const labels = computeTriangleLabels(spec);
  const layout = scaleToFit(spec.base, spec.height, screenWidth - 48);
  const offsetX = 48;
  const offsetY = 28;
  const b = layout.w;
  const h = layout.h;
  const raw = baseHeightTriangleVertices(b, h);
  const x0 = offsetX + raw.x0;
  const y0 = offsetY + raw.y0;
  const x1 = offsetX + raw.x1;
  const y1 = offsetY + raw.y1;
  const x2 = offsetX + raw.x2;
  const y2 = offsetY + raw.y2;
  const svgW = b + offsetX + 48;
  const svgH = h + offsetY + 36;
  const showLabels = spec.show_labels !== false;
  const showTicks = shouldShowTicks(spec.show_ticks, false);
  const showAltitude = spec.show_altitude !== false;
  const showAngle = spec.show_angle !== false;
  let verts = [
    { x: x0, y: y0 },
    { x: x1, y: y1 },
    { x: x2, y: y2 },
  ];
  let outW = svgW;
  let outH = svgH;
  if (showAngle) {
    const padded = padDiagramForAngleLabels(verts, svgW, svgH);
    verts = padded.vertices;
    outW = padded.svgW;
    outH = padded.svgH;
  }
  const tickSegments = showTicks
    ? [...sideTickMarks(verts[0].x, verts[0].y, verts[2].x, verts[2].y, 1), ...sideTickMarks(verts[1].x, verts[1].y, verts[2].x, verts[2].y, 1)]
    : [];

  return (
    <Svg width={outW} height={outH}>
      <Polygon
        points={`${verts[0].x},${verts[0].y} ${verts[1].x},${verts[1].y} ${verts[2].x},${verts[2].y}`}
        fill={theme.contentSurface}
        stroke={theme.primary}
        strokeWidth={2}
        accessibilityLabel="triangle-outline"
      />
      {showAltitude ? (
        <Line
          x1={verts[2].x}
          y1={verts[2].y}
          x2={verts[2].x}
          y2={verts[0].y}
          stroke={colors.height}
          strokeWidth={2}
          strokeDasharray="5,4"
          accessibilityLabel="altitude-line"
        />
      ) : null}
      {tickSegments.length > 0 ? <TickMarks segments={tickSegments} color={theme.textSecondary} /> : null}
      {showAngle ? (
        <InteriorAngleMarks vertices={verts} color={theme.textSecondary} fill={theme.contentSurface} />
      ) : null}
      {showLabels ? (
        <>
          <SvgText
            x={(verts[0].x + verts[1].x) / 2}
            y={verts[0].y + 18}
            fill={theme.text}
            fontSize={13}
            fontWeight="600"
            textAnchor="middle"
          >
            {labels.base}
          </SvgText>
          <SvgText
            x={verts[2].x + 10}
            y={(verts[2].y + verts[0].y) / 2}
            fill={colors.height}
            fontSize={12}
            fontWeight="600"
          >
            {labels.height}
          </SvgText>
          <SvgText x={verts[2].x} y={verts[2].y - 8} fill={theme.textSecondary} fontSize={11} textAnchor="middle">
            {labels.area}
          </SvgText>
        </>
      ) : null}
    </Svg>
  );
}

function RightTriangleDiagram({
  spec,
  screenWidth,
  theme,
}: {
  spec: RightTriangleSpec;
  screenWidth: number;
  theme: Theme;
}) {
  const colors = diagramColors(theme);
  const labels = computeRightTriangleLabels(spec);
  const layout = scaleToFit(spec.base, spec.height, screenWidth - 48);
  const offsetX = 48;
  const offsetY = 28;
  const b = layout.w;
  const h = layout.h;
  const x0 = offsetX;
  const y0 = offsetY;
  const x1 = offsetX + b;
  const y1 = offsetY + h;
  const svgW = b + offsetX + 48;
  const svgH = h + offsetY + 40;
  const showLabels = spec.show_labels !== false;
  const showHyp = spec.show_hypotenuse !== false;
  const showAngle = spec.show_angle !== false;
  let verts = [
    { x: x0, y: y1 },
    { x: x1, y: y1 },
    { x: x0, y: y0 },
  ];
  let outW = svgW;
  let outH = svgH;
  if (showAngle) {
    const padded = padDiagramForAngleLabels(verts, svgW, svgH);
    verts = padded.vertices;
    outW = padded.svgW;
    outH = padded.svgH;
  }

  return (
    <Svg width={outW} height={outH}>
      <Polygon
        points={`${verts[0].x},${verts[0].y} ${verts[1].x},${verts[1].y} ${verts[2].x},${verts[2].y}`}
        fill={theme.contentSurface}
        stroke={theme.primary}
        strokeWidth={2}
      />
      {showAngle ? (
        <InteriorAngleMarks vertices={verts} color={theme.textSecondary} fill={theme.contentSurface} />
      ) : null}
      {showLabels ? (
        <>
          <SvgText
            x={(verts[0].x + verts[1].x) / 2}
            y={verts[0].y + 18}
            fill={theme.text}
            fontSize={13}
            fontWeight="600"
            textAnchor="middle"
          >
            {labels.base}
          </SvgText>
          <SvgText
            x={verts[0].x - 10}
            y={(verts[2].y + verts[0].y) / 2}
            fill={colors.height}
            fontSize={12}
            fontWeight="600"
            textAnchor="end"
          >
            {labels.height}
          </SvgText>
          {showHyp ? (
            <SvgText
              x={(verts[0].x + verts[1].x) / 2 + 8}
              y={(verts[2].y + verts[0].y) / 2 - 6}
              fill={colors.hypotenuse}
              fontSize={12}
              fontWeight="600"
            >
              {labels.hypotenuse}
            </SvgText>
          ) : null}
        </>
      ) : null}
    </Svg>
  );
}

function CircleDiagram({ spec, screenWidth, theme }: { spec: CircleSpec; screenWidth: number; theme: Theme }) {
  const colors = diagramColors(theme);
  const labels = computeCircleLabels(spec);
  const layout = scaleToFit(spec.radius * 2, spec.radius * 2, screenWidth - 48);
  const r = layout.w / 2;
  const offsetX = 40;
  const offsetY = 36;
  const cx = offsetX + r;
  const cy = offsetY + r;
  const svgW = r * 2 + offsetX * 2;
  const extraLines = [spec.show_diameter, spec.show_area, spec.show_circumference].filter(
    Boolean,
  ).length;
  const svgH = r * 2 + offsetY * 2 + (extraLines > 0 ? 16 * extraLines + 20 : 0);
  const showLabels = spec.show_labels !== false;

  return (
    <Svg width={svgW} height={svgH}>
      <Circle cx={cx} cy={cy} r={r} fill={theme.contentSurface} stroke={theme.primary} strokeWidth={2} />
      <Line x1={cx} y1={cy} x2={cx + r} y2={cy} stroke={colors.diagonal} strokeWidth={2} strokeDasharray="6,4" />
      {showLabels ? (
        <SvgText x={cx + r / 2} y={cy - 8} fill={colors.diagonal} fontSize={12} fontWeight="600" textAnchor="middle">
          {labels.radius}
        </SvgText>
      ) : null}
      {spec.show_diameter ? (
        <SvgText x={cx} y={cy + r + 34} fill={theme.textSecondary} fontSize={12} textAnchor="middle">
          {`${i18n.t("rich.diameter")}\u00A0${labels.diameter}`}
        </SvgText>
      ) : null}
      {spec.show_area ? (
        <SvgText
          x={cx}
          y={cy + r + 34 + (spec.show_diameter ? 16 : 0)}
          fill={theme.textSecondary}
          fontSize={12}
          textAnchor="middle"
        >
          {`${i18n.t("rich.area")}\u00A0${labels.area}`}
        </SvgText>
      ) : null}
      {spec.show_circumference ? (
        <SvgText
          x={cx}
          y={cy + r + 34 + (spec.show_diameter ? 16 : 0) + (spec.show_area ? 16 : 0)}
          fill={theme.textSecondary}
          fontSize={12}
          textAnchor="middle"
        >
          {`${i18n.t("rich.circumference")}\u00A0${labels.circumference}`}
        </SvgText>
      ) : null}
    </Svg>
  );
}

function TriangleSidesDiagram({
  spec,
  screenWidth,
  theme,
}: {
  spec: TriangleSidesSpec;
  screenWidth: number;
  theme: Theme;
}) {
  const colors = diagramColors(theme);
  const labels = computeTriangleSidesLabels(spec);
  const raw = triangleSidesVertices(spec.a, spec.b, spec.c);
  const maxX = Math.max(raw.x0, raw.x1, raw.x2);
  const maxY = Math.max(raw.y0, raw.y1, raw.y2, 1);
  const inner = Math.max(screenWidth - 48 - 80, 120);
  const scale = inner / Math.max(maxX, maxY, 1);
  const offsetX = 40;
  const offsetY = 28;
  // SVG y grows downward \u2014 flip so the apex draws above the base.
  const toSvg = (x: number, y: number) => ({
    x: offsetX + x * scale,
    y: offsetY + (maxY - y) * scale,
  });
  const p0raw = toSvg(raw.x0, raw.y0);
  const p1raw = toSvg(raw.x1, raw.y1);
  const p2raw = toSvg(raw.x2, raw.y2);
  const showLabels = spec.show_labels !== false;
  const svgW0 = maxX * scale + offsetX * 2;
  const labelBelow = showLabels ? 52 : 16;
  const svgH0 = maxY * scale + offsetY + labelBelow;
  const tickCounts = equalSideTickCounts(spec.a, spec.b, spec.c);
  const hasEqualSides = tickCounts.a > 0 || tickCounts.b > 0 || tickCounts.c > 0;
  const showTicks = shouldShowTicks(spec.show_ticks, hasEqualSides);
  const showAltitude = spec.show_altitude === true;
  const showAngle = spec.show_angle !== false;
  let verts = [p0raw, p1raw, p2raw];
  let svgW = svgW0;
  let svgH = svgH0;
  if (showAngle) {
    const padded = padDiagramForAngleLabels(verts, svgW, svgH);
    verts = padded.vertices;
    svgW = padded.svgW;
    svgH = padded.svgH;
  }
  const [p0, p1, p2] = verts;
  const showMedian =
    spec.show_median === true || (spec.show_median !== false && isIsoscelesSides(spec.a, spec.b, spec.c));
  const foot = footOfPerpendicular(p0.x, p0.y, p1.x, p1.y, p2.x, p2.y);
  const mid = midpoint(p0.x, p0.y, p1.x, p1.y);
  // When altitude and median coincide (isosceles with base a), draw one line.
  const altitudeIsMedian =
    Math.hypot(foot.x - mid.x, foot.y - mid.y) < 1.5;
  const tickSegments = showTicks
    ? [
        ...sideTickMarks(p0.x, p0.y, p1.x, p1.y, tickCounts.a),
        ...sideTickMarks(p1.x, p1.y, p2.x, p2.y, tickCounts.b),
        ...sideTickMarks(p2.x, p2.y, p0.x, p0.y, tickCounts.c),
      ]
    : [];

  return (
    <Svg width={svgW} height={svgH} testID="sss-svg">
      <Polygon
        points={`${p0.x},${p0.y} ${p1.x},${p1.y} ${p2.x},${p2.y}`}
        fill={theme.contentSurface}
        stroke={theme.primary}
        strokeWidth={2}
      />
      {showAltitude ? (
        <Line
          x1={p2.x}
          y1={p2.y}
          x2={foot.x}
          y2={foot.y}
          stroke={colors.height}
          strokeWidth={2}
          strokeDasharray="5,4"
          accessibilityLabel="altitude-line"
        />
      ) : null}
      {showMedian && !altitudeIsMedian ? (
        <Line
          x1={p2.x}
          y1={p2.y}
          x2={mid.x}
          y2={mid.y}
          stroke={colors.median}
          strokeWidth={1.5}
          strokeDasharray="2,3"
          accessibilityLabel="median-line"
        />
      ) : null}
      {showMedian && altitudeIsMedian && !showAltitude ? (
        <Line
          x1={p2.x}
          y1={p2.y}
          x2={mid.x}
          y2={mid.y}
          stroke={colors.median}
          strokeWidth={1.5}
          strokeDasharray="2,3"
          accessibilityLabel="median-line"
        />
      ) : null}
      {tickSegments.length > 0 ? <TickMarks segments={tickSegments} color={theme.textSecondary} /> : null}
      {showAngle ? (
        <InteriorAngleMarks
          vertices={[p0, p1, p2]}
          color={theme.textSecondary}
          fill={theme.contentSurface}
        />
      ) : null}
      {showLabels ? (
        <>
          <SvgText x={(p0.x + p1.x) / 2} y={p0.y + 18} fill={theme.text} fontSize={13} fontWeight="600" textAnchor="middle">
            {labels.a}
          </SvgText>
          <SvgText x={(p1.x + p2.x) / 2 + 8} y={(p1.y + p2.y) / 2} fill={theme.text} fontSize={13} fontWeight="600">
            {labels.b}
          </SvgText>
          <SvgText x={(p2.x + p0.x) / 2 - 8} y={(p2.y + p0.y) / 2} fill={theme.text} fontSize={13} fontWeight="600" textAnchor="end">
            {labels.c}
          </SvgText>
          <SvgText
            x={(p0.x + p1.x + p2.x) / 3}
            y={Math.max(p0.y, p1.y) + 34}
            fill={theme.textSecondary}
            fontSize={12}
            textAnchor="middle"
            testID="sss-area-label"
          >
            {`${i18n.t("rich.area")}\u00A0${labels.area}`}
          </SvgText>
        </>
      ) : null}
    </Svg>
  );
}

function TrapezoidDiagram({
  spec,
  screenWidth,
  theme,
}: {
  spec: TrapezoidSpec;
  screenWidth: number;
  theme: Theme;
}) {
  const labels = computeTrapezoidLabels(spec);
  const inner = Math.max(screenWidth - 48 - 80, 120);
  const scale = inner / Math.max(spec.top, spec.bottom, spec.height, 1);
  const topW = spec.top * scale;
  const bottomW = spec.bottom * scale;
  const h = spec.height * scale;
  const offsetX = 40;
  const offsetY = 28;
  const bx0 = offsetX;
  const bx1 = offsetX + bottomW;
  const by = offsetY + h;
  const tx0 = offsetX + (bottomW - topW) / 2;
  const tx1 = tx0 + topW;
  const ty = offsetY;
  const svgW = bottomW + offsetX * 2;
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

function ParallelogramDiagram({
  spec,
  screenWidth,
  theme,
}: {
  spec: ParallelogramSpec;
  screenWidth: number;
  theme: Theme;
}) {
  const labels = computeParallelogramLabels(spec);
  const { svgW, svgH, bx0, bx1, by, tx0, tx1, ty } = parallelogramLayout(spec, screenWidth);
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
          <SvgText x={(bl.x + br.x) / 2} y={bl.y + 18} fill={theme.text} fontSize={13} fontWeight="600" textAnchor="middle">
            {labels.base}
          </SvgText>
          <SvgText x={tl.x - 8} y={(tl.y + bl.y) / 2} fill={theme.accent} fontSize={12} fontWeight="600" textAnchor="end">
            {labels.height}
          </SvgText>
          <SvgText x={(tl.x + bl.x) / 2 + 6} y={(tl.y + bl.y) / 2 - 10} fill={theme.text} fontSize={12} fontWeight="600">
            {labels.side}
          </SvgText>
          <SvgText x={(bl.x + br.x) / 2} y={bl.y + 34} fill={theme.textSecondary} fontSize={12} textAnchor="middle">
            {`${i18n.t("rich.area")}\u00A0${labels.area}`}
          </SvgText>
        </>
      ) : null}
    </Svg>
  );
}

function SectorDiagram({
  spec,
  screenWidth,
  theme,
}: {
  spec: SectorSpec;
  screenWidth: number;
  theme: Theme;
}) {
  const labels = computeSectorLabels(spec);
  const layout = scaleToFit(spec.radius * 2, spec.radius * 2, screenWidth - 48);
  const r = layout.w / 2;
  const offsetX = 40;
  const offsetY = 36;
  const cx = offsetX + r;
  const cy = offsetY + r;
  // Sweep clockwise from straight up (12 o'clock) by angle_deg.
  const startRad = (-90 * Math.PI) / 180;
  const endRad = ((-90 + spec.angle_deg) * Math.PI) / 180;
  const x1 = cx + r * Math.cos(startRad);
  const y1 = cy + r * Math.sin(startRad);
  const x2 = cx + r * Math.cos(endRad);
  const y2 = cy + r * Math.sin(endRad);
  const largeArc = spec.angle_deg > 180 ? 1 : 0;
  const path = `M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${largeArc} 1 ${x2},${y2} Z`;
  const midRad = (startRad + endRad) / 2;
  const labelR = r * 0.55;
  const svgW = r * 2 + offsetX * 2;
  const svgH = r * 2 + offsetY * 2 + 40;
  const showLabels = spec.show_labels !== false;

  return (
    <Svg width={svgW} height={svgH}>
      <Path d={path} fill={theme.contentSurface} stroke={theme.primary} strokeWidth={2} />
      {showLabels ? (
        <>
          <SvgText
            x={cx + labelR * Math.cos(midRad)}
            y={cy + labelR * Math.sin(midRad)}
            fill={theme.text}
            fontSize={12}
            fontWeight="600"
            textAnchor="middle"
          >
            {labels.angle}
          </SvgText>
          <SvgText x={(cx + x1) / 2 - 6} y={(cy + y1) / 2} fill={theme.accent} fontSize={12} fontWeight="600" textAnchor="end">
            {labels.radius}
          </SvgText>
          <SvgText x={cx} y={cy + r + 34} fill={theme.textSecondary} fontSize={12} textAnchor="middle">
            {`${i18n.t("rich.area")}\u00A0${labels.area}`}
          </SvgText>
          <SvgText x={cx} y={cy + r + 50} fill={theme.textSecondary} fontSize={12} textAnchor="middle">
            {`${i18n.t("rich.arc_length")}\u00A0${labels.arc_length}`}
          </SvgText>
        </>
      ) : null}
    </Svg>
  );
}

export function GeometryBlock({ content }: Props) {
  const theme = useTheme();
  const { width: screenWidth } = useWindowDimensions();
  const spec = useMemo(() => parseGeometrySpec(content), [content]);
  const styles = useMemo(() => makeStyles(theme), [theme]);

  if (!spec) {
    return (
      <View style={styles.fallback}>
        <Text style={styles.fallbackText}>{i18n.t("rich.geometry_error")}</Text>
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      {spec.type === "right_triangle" ? (
        <RightTriangleDiagram spec={spec} screenWidth={screenWidth} theme={theme} />
      ) : spec.type === "triangle" ? (
        <TriangleDiagram spec={spec} screenWidth={screenWidth} theme={theme} />
      ) : spec.type === "triangle_sides" ? (
        <TriangleSidesDiagram spec={spec} screenWidth={screenWidth} theme={theme} />
      ) : spec.type === "trapezoid" ? (
        <TrapezoidDiagram spec={spec} screenWidth={screenWidth} theme={theme} />
      ) : spec.type === "parallelogram" ? (
        <ParallelogramDiagram spec={spec} screenWidth={screenWidth} theme={theme} />
      ) : spec.type === "sector" ? (
        <SectorDiagram spec={spec} screenWidth={screenWidth} theme={theme} />
      ) : spec.type === "circle" ? (
        <CircleDiagram spec={spec} screenWidth={screenWidth} theme={theme} />
      ) : (
        <RectangleDiagram spec={spec} screenWidth={screenWidth} theme={theme} />
      )}
    </View>
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    wrap: {
      marginVertical: 8,
      alignItems: "center",
    },
    fallback: {
      marginVertical: 8,
      padding: 12,
      borderRadius: 10,
      backgroundColor: theme.contentSurface,
    },
    fallbackText: {
      color: theme.textSecondary,
      fontSize: 14,
    },
  });
