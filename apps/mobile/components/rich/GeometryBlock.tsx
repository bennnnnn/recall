import { useMemo } from "react";
import { StyleSheet, Text, useWindowDimensions, View } from "react-native";
import Svg, { Circle, Line, Polygon, Rect, Text as SvgText } from "react-native-svg";

import {
  computeCircleLabels,
  computeRectangleLabels,
  computeRightTriangleLabels,
  computeTriangleLabels,
  parseGeometrySpec,
  rectangleAngleDisplay,
  scaleToFit,
  type CircleSpec,
  type RectangleSpec,
  type RightTriangleSpec,
  type TriangleSpec,
} from "@/lib/geometryBlock";
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
          {`Area:\u00A0${labels.area}`}
        </SvgText>
      ) : null}
      {spec.show_perimeter ? (
        <SvgText x={x + w / 2} y={y + h + (spec.show_area ? 50 : 34)} fill={theme.textSecondary} fontSize={12} textAnchor="middle">
          {`Perimeter:\u00A0${labels.perimeter}`}
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
          {`Diameter:\u00A0${labels.diameter}`}
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
          {`Area:\u00A0${labels.area}`}
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
          {`Circumference:\u00A0${labels.circumference}`}
        </SvgText>
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
        <Text style={styles.fallbackText}>Could not render geometry diagram.</Text>
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      {spec.type === "right_triangle" ? (
        <RightTriangleDiagram spec={spec} screenWidth={screenWidth} theme={theme} />
      ) : spec.type === "triangle" ? (
        <TriangleDiagram spec={spec} screenWidth={screenWidth} theme={theme} />
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
