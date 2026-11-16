import { useMemo } from "react";
import { StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { useTranslation } from "react-i18next";

import { CoordinatePlaneChart } from "@/components/rich/CoordinatePlaneChart";
import { NumberLineChart } from "@/components/rich/NumberLineChart";
import { InequalityGraphChart } from "@/components/rich/InequalityGraphChart";
import { InteractiveFunctionPlot } from "@/components/rich/InteractiveFunctionPlot";
import { PlotGraphCard } from "@/components/rich/PlotGraphCard";
import { TrajectoryChart } from "@/components/rich/TrajectoryChart";
import { figureTitleStyle, figureWidth } from "@/components/rich/figure";
import { NUMBER_LINE_HEIGHT } from "@/components/rich/graphPlaceholder";
import { useFenceRefused } from "@/components/rich/useFenceRefused";
import { formatGraphExpr, formatInequalityExpr } from "@/lib/math/graphBlock";
import { GRAPH_KINDS, parseGraphSpec } from "@/lib/math/graphSpec";
import { parsePlotGraph } from "@/lib/math/plotGraph";
import { parsePointsGraph } from "@/lib/math/pointsGraph";
import { Theme, useTheme } from "@/lib/theme";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";

type Props = { content: string };

const GRAPH_BODY = { json: true, kinds: { field: "type", known: GRAPH_KINDS } };

export function FunctionGraphBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const { width: screenWidth } = useWindowDimensions();
  const spec = useMemo(() => parseGraphSpec(content), [content]);
  const plane = useMemo(() => (spec ? null : parsePointsGraph(content)), [content, spec]);
  const plot = useMemo(() => (spec || plane ? null : parsePlotGraph(content)), [content, spec, plane]);
  const styles = useMemo(() => makeStyles(theme), [theme]);
  const chartWidth = figureWidth(screenWidth);
  useFenceRefused("graph", content, spec === null && plane === null && plot === null, GRAPH_BODY);

  if (plot) {
    return <PlotGraphCard graph={plot} width={chartWidth} theme={theme} />;
  }

  if (plane) {
    return <CoordinatePlaneChart graph={plane} width={chartWidth} theme={theme} styles={styles} />;
  }

  if (!spec) {
    return (
      <View style={styles.fallback}>
        <Text style={styles.fallbackText}>
          {t("rich.graph_error")}
        </Text>
      </View>
    );
  }

  if (spec.type === "number_line") {
    return (
      <View style={styles.wrap}>
        <Text style={styles.title}>
          {formatInequalityExpr(formatGraphExpr(spec.title ?? spec.expr))}
        </Text>
        <NumberLineChart
          spec={spec}
          width={chartWidth}
          height={NUMBER_LINE_HEIGHT}
          color={theme.primary}
          axisColor={theme.border}
          labelColor={theme.textSecondary}
          surfaceColor={theme.bg}
        />
      </View>
    );
  }

  if (spec.type === "inequality") {
    return <InequalityGraphChart spec={spec} width={chartWidth} />;
  }

  if (spec.type === "trajectory") {
    return (
      <TrajectoryChart
        spec={spec}
        chartWidth={chartWidth}
        styles={styles}
        theme={theme}
      />
    );
  }

  return (
    <InteractiveFunctionPlot
      key={spec.expr}
      spec={spec}
      chartWidth={chartWidth}
      styles={styles}
      theme={theme}
    />
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    wrap: {
      marginVertical: Space.xs,
      alignItems: "center",
    },
    title: figureTitleStyle(theme),
    fallback: {
      marginVertical: Space.xs,
      padding: Space.sm,
      borderRadius: Radius.sm,
      backgroundColor: theme.contentSurface,
    },
    fallbackText: {
      color: theme.textSecondary,
      ...Type.secondary,
    },
  });
