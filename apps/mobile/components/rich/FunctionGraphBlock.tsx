import { useMemo } from "react";
import { StyleSheet, Text, useWindowDimensions, View } from "react-native";
import Svg, { Line, Polyline, Text as SvgText } from "react-native-svg";

import { graphBounds, graphPolylinePoints, parseGraphSpec } from "@/lib/graphBlock";
import { CODE_FONT } from "@/lib/fonts";
import { Theme, useTheme } from "@/lib/theme";

type Props = { content: string };

const CHART_HEIGHT = 220;

export function FunctionGraphBlock({ content }: Props) {
  const theme = useTheme();
  const { width: screenWidth } = useWindowDimensions();
  const spec = useMemo(() => parseGraphSpec(content), [content]);
  const styles = useMemo(() => makeStyles(theme), [theme]);
  const chartWidth = Math.min(screenWidth - 48, 360);

  if (!spec) {
    return (
      <View style={styles.fallback}>
        <Text style={styles.fallbackText}>Could not render function graph.</Text>
      </View>
    );
  }

  const bounds = graphBounds(spec.points);
  const polyline = graphPolylinePoints(spec.points, chartWidth, CHART_HEIGHT);
  const pad = 28;
  const axisColor = theme.border;
  const xAxisY = CHART_HEIGHT - pad;
  const yAxisX = pad;

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{spec.title ?? `y = ${spec.expr}`}</Text>
      <Svg width={chartWidth} height={CHART_HEIGHT}>
        <Line
          x1={yAxisX}
          y1={pad}
          x2={yAxisX}
          y2={xAxisY}
          stroke={axisColor}
          strokeWidth={1}
        />
        <Line
          x1={yAxisX}
          y1={xAxisY}
          x2={chartWidth - pad}
          y2={xAxisY}
          stroke={axisColor}
          strokeWidth={1}
        />
        <Polyline
          points={polyline}
          fill="none"
          stroke={theme.primary}
          strokeWidth={2.5}
        />
        <SvgText x={chartWidth - pad - 4} y={xAxisY + 16} fill={theme.textSecondary} fontSize={11}>
          {spec.variable}
        </SvgText>
        <SvgText x={4} y={pad + 4} fill={theme.textSecondary} fontSize={11}>
          {bounds.yMax.toFixed(1)}
        </SvgText>
      </Svg>
    </View>
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    wrap: {
      marginVertical: 8,
      alignItems: "center",
    },
    title: {
      fontFamily: CODE_FONT,
      fontSize: 14,
      color: theme.text,
      marginBottom: 6,
      textAlign: "center",
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
