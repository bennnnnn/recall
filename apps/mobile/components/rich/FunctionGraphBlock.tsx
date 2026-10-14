import { useMemo } from "react";
import { StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { useTranslation } from "react-i18next";

import { NumberLineChart } from "@/components/rich/NumberLineChart";
import { InequalityGraphChart } from "@/components/rich/InequalityGraphChart";
import { InteractiveFunctionPlot } from "@/components/rich/InteractiveFunctionPlot";
import { TrajectoryChart } from "@/components/rich/TrajectoryChart";
import { figureTitleStyle, figureWidth } from "@/components/rich/figure";
import { formatGraphExpr, formatInequalityExpr } from "@/lib/math/graphBlock";
import { parseGraphSpec } from "@/lib/math/graphSpec";
import { CODE_FONT } from "@/lib/fonts";
import { Theme, useTheme } from "@/lib/theme";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";

type Props = { content: string };

const NUMBER_LINE_HEIGHT = 80;

export function FunctionGraphBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const { width: screenWidth } = useWindowDimensions();
  const spec = useMemo(() => parseGraphSpec(content), [content]);
  const styles = useMemo(() => makeStyles(theme), [theme]);
  const chartWidth = figureWidth(screenWidth);

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
    legendRow: {
      flexDirection: "row",
      gap: Space.md,
      marginBottom: Space.xs,
    },
    legendItem: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
    },
    legendDot: {
      width: 8,
      height: 8,
      borderRadius: Radius.full,
    },
    legendText: {
      fontFamily: CODE_FONT,
      fontSize: 12,
      color: theme.textSecondary,
    },
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
