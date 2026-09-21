import { useMemo } from "react";
import { StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { useTranslation } from "react-i18next";

import { NumberLineChart } from "@/components/rich/NumberLineChart";
import { InequalityGraphChart } from "@/components/rich/InequalityGraphChart";
import { InteractiveFunctionPlot } from "@/components/rich/InteractiveFunctionPlot";
import { TrajectoryChart } from "@/components/rich/TrajectoryChart";
import {
  formatGraphExpr,
  formatInequalityExpr,
  parseGraphSpec,
} from "@/lib/math/graphBlock";
import { CODE_FONT } from "@/lib/fonts";
import { Theme, useTheme } from "@/lib/theme";

type Props = { content: string };

const NUMBER_LINE_HEIGHT = 80;

export function FunctionGraphBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const { width: screenWidth } = useWindowDimensions();
  const spec = useMemo(() => parseGraphSpec(content), [content]);
  const styles = useMemo(() => makeStyles(theme), [theme]);
  const chartWidth = Math.min(screenWidth - 48, 360);

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
      marginVertical: 8,
      alignItems: "center",
    },
    title: {
      fontSize: 15,
      fontWeight: "600",
      color: theme.text,
      marginBottom: 2,
      textAlign: "center",
    },
    legendRow: {
      flexDirection: "row",
      gap: 16,
      marginBottom: 8,
    },
    legendItem: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
    },
    legendDot: {
      width: 8,
      height: 8,
      borderRadius: 4,
    },
    legendText: {
      fontFamily: CODE_FONT,
      fontSize: 12,
      color: theme.textSecondary,
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
