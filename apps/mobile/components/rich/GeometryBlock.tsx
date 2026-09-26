import { useMemo } from "react";
import { StyleSheet, Text, useWindowDimensions, View } from "react-native";

import { CircleDiagram } from "@/components/rich/geometry/CircleDiagram";
import { ParallelogramDiagram } from "@/components/rich/geometry/ParallelogramDiagram";
import { RectangleDiagram } from "@/components/rich/geometry/RectangleDiagram";
import { RightTriangleDiagram } from "@/components/rich/geometry/RightTriangleDiagram";
import { SectorDiagram } from "@/components/rich/geometry/SectorDiagram";
import { TrapezoidDiagram } from "@/components/rich/geometry/TrapezoidDiagram";
import { TriangleDiagram } from "@/components/rich/geometry/TriangleDiagram";
import { TriangleSidesDiagram } from "@/components/rich/geometry/TriangleSidesDiagram";
import i18n from "@/lib/i18n";
import { parseGeometrySpec } from "@/lib/math/geometryBlock";
import { Theme, useTheme } from "@/lib/theme";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";

type Props = { content: string };

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
      marginVertical: Space.xs,
      alignItems: "center",
    },
    fallback: {
      marginVertical: Space.xs,
      padding: Space.sm,
      borderRadius: Radius.sm,
      backgroundColor: theme.contentSurface,
    },
    fallbackText: {
      color: theme.textSecondary,
      fontSize: 14,
    },
  });
