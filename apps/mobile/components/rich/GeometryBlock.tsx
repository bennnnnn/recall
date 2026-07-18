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
  parseGeometrySpec,
  rectangleAngleDisplay,
  scaleToFit,
  triangleSidesVertices,
  type CircleSpec,
  type ParallelogramSpec,
  type RectangleSpec,
  type RightTriangleSpec,
  type SectorSpec,
  type TrapezoidSpec,
  type TriangleSidesSpec,
  type TriangleSpec,
} from "@/lib/geometryBlock";
import i18n from "@/lib/i18n";
import { Theme, useTheme } from "@/lib/theme";

type Props = { content: string };

function diagramColors(theme: Theme) {
  return {
    diagonal: theme.danger,
    height: theme.accent,
    hypotenuse: theme.danger,
  };
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
        // This is the angle the diagonal makes with the base — NOT the
        // rectangle's own corner angle (always 90°, shown by the bracket
        // glyph above when no diagonal is drawn). Labeling it "∠" avoids
        // it reading as a contradiction of that right angle.
        <SvgText x={x + 12} y={y + h - 8} fill={theme.textSecondary} fontSize={12}>
          {`∠\u00A0${labels.angle}`}
        </SvgText>
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
  const x0 = offsetX;
  const y0 = offsetY + h;
  const x1 = offsetX + b;
  const y1 = offsetY + h;
  const x2 = offsetX + b / 2;
  const y2 = offsetY;
  const svgW = b + offsetX + 48;
  const svgH = h + offsetY + 36;
  const showLabels = spec.show_labels !== false;

  return (
    <Svg width={svgW} height={svgH}>
      <Polygon
        points={`${x0},${y0} ${x1},${y1} ${x2},${y2}`}
        fill={theme.contentSurface}
        stroke={theme.primary}
        strokeWidth={2}
      />
      <Line
        x1={x2}
        y1={y2}
        x2={x2}
        y2={y0}
        stroke={colors.height}
        strokeWidth={2}
        strokeDasharray="5,4"
      />
      {showLabels ? (
        <>
          <SvgText x={(x0 + x1) / 2} y={y0 + 18} fill={theme.text} fontSize={13} fontWeight="600" textAnchor="middle">
            {labels.base}
          </SvgText>
          <SvgText x={x2 + 10} y={(y2 + y0) / 2} fill={colors.height} fontSize={12} fontWeight="600">
            {labels.height}
          </SvgText>
          <SvgText x={x2} y={y2 - 8} fill={theme.textSecondary} fontSize={11} textAnchor="middle">
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
  const offsetX = 56;
  const offsetY = 28;
  const b = layout.w;
  const h = layout.h;
  const x0 = offsetX;
  const y0 = offsetY;
  const x1 = offsetX + b;
  const y1 = offsetY + h;
  const svgW = b + offsetX + 56;
  const svgH = h + offsetY + 40;
  const showLabels = spec.show_labels !== false;
  const showHyp = spec.show_hypotenuse !== false;
  const showAngle = spec.show_angle !== false;
  const corner = 14;

  return (
    <Svg width={svgW} height={svgH}>
      <Polygon
        points={`${x0},${y1} ${x1},${y1} ${x0},${y0}`}
        fill={theme.contentSurface}
        stroke={theme.primary}
        strokeWidth={2}
      />
      {showAngle ? (
        <Polygon
          points={`${x0},${y1} ${x0 + corner},${y1} ${x0 + corner},${y1 - corner} ${x0},${y1 - corner}`}
          fill="none"
          stroke={theme.textSecondary}
          strokeWidth={1.5}
        />
      ) : null}
      {showLabels ? (
        <>
          <SvgText x={(x0 + x1) / 2} y={y1 + 18} fill={theme.text} fontSize={13} fontWeight="600" textAnchor="middle">
            {labels.base}
          </SvgText>
          <SvgText x={x0 - 10} y={(y0 + y1) / 2} fill={colors.height} fontSize={12} fontWeight="600" textAnchor="end">
            {labels.height}
          </SvgText>
          {showHyp ? (
            <SvgText
              x={(x0 + x1) / 2 + 8}
              y={(y0 + y1) / 2 - 6}
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
  const p0 = toSvg(raw.x0, raw.y0);
  const p1 = toSvg(raw.x1, raw.y1);
  const p2 = toSvg(raw.x2, raw.y2);
  const svgW = maxX * scale + offsetX * 2;
  const svgH = maxY * scale + offsetY + 36;
  const showLabels = spec.show_labels !== false;

  return (
    <Svg width={svgW} height={svgH}>
      <Polygon
        points={`${p0.x},${p0.y} ${p1.x},${p1.y} ${p2.x},${p2.y}`}
        fill={theme.contentSurface}
        stroke={theme.primary}
        strokeWidth={2}
      />
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
          <SvgText x={(p0.x + p1.x + p2.x) / 3} y={Math.max(p0.y, p1.y) + 34} fill={theme.textSecondary} fontSize={12} textAnchor="middle">
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

  return (
    <Svg width={svgW} height={svgH}>
      <Polygon
        points={`${tx0},${ty} ${tx1},${ty} ${bx1},${by} ${bx0},${by}`}
        fill={theme.contentSurface}
        stroke={theme.primary}
        strokeWidth={2}
      />
      <Line x1={tx0} y1={ty} x2={tx0} y2={by} stroke={theme.accent} strokeWidth={2} strokeDasharray="5,4" />
      {showLabels ? (
        <>
          <SvgText x={(tx0 + tx1) / 2} y={ty - 8} fill={theme.text} fontSize={13} fontWeight="600" textAnchor="middle">
            {labels.top}
          </SvgText>
          <SvgText x={(bx0 + bx1) / 2} y={by + 18} fill={theme.text} fontSize={13} fontWeight="600" textAnchor="middle">
            {labels.bottom}
          </SvgText>
          <SvgText x={tx0 - 8} y={(ty + by) / 2} fill={theme.accent} fontSize={12} fontWeight="600" textAnchor="end">
            {labels.height}
          </SvgText>
          <SvgText x={(bx0 + bx1) / 2} y={by + 34} fill={theme.textSecondary} fontSize={12} textAnchor="middle">
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
  const inner = Math.max(screenWidth - 48 - 80, 120);
  const scale = inner / Math.max(spec.base, spec.side, 1);
  const b = spec.base * scale;
  const h = spec.height * scale;
  const s = spec.side * scale;
  // Horizontal shear of the top edge \u2014 the slant side is the hypotenuse of
  // the right triangle formed by the height and this shear.
  const shear = Math.sqrt(Math.max(0, s * s - h * h));
  const offsetX = 40 + shear;
  const offsetY = 28;
  const bx0 = offsetX;
  const bx1 = offsetX + b;
  const by = offsetY + h;
  const tx0 = offsetX - shear;
  const tx1 = tx0 + b;
  const ty = offsetY;
  const svgW = b + shear + offsetX + 40;
  const svgH = h + offsetY + 40;
  const showLabels = spec.show_labels !== false;

  return (
    <Svg width={svgW} height={svgH}>
      <Polygon
        points={`${tx0},${ty} ${tx1},${ty} ${bx1},${by} ${bx0},${by}`}
        fill={theme.contentSurface}
        stroke={theme.primary}
        strokeWidth={2}
      />
      <Line x1={tx0} y1={ty} x2={tx0} y2={by} stroke={theme.accent} strokeWidth={2} strokeDasharray="5,4" />
      {showLabels ? (
        <>
          <SvgText x={(bx0 + bx1) / 2} y={by + 18} fill={theme.text} fontSize={13} fontWeight="600" textAnchor="middle">
            {labels.base}
          </SvgText>
          <SvgText x={tx0 - 8} y={(ty + by) / 2} fill={theme.accent} fontSize={12} fontWeight="600" textAnchor="end">
            {labels.height}
          </SvgText>
          <SvgText x={(tx0 + bx0) / 2 + 6} y={(ty + by) / 2 - 10} fill={theme.text} fontSize={12} fontWeight="600">
            {labels.side}
          </SvgText>
          <SvgText x={(bx0 + bx1) / 2} y={by + 34} fill={theme.textSecondary} fontSize={12} textAnchor="middle">
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
