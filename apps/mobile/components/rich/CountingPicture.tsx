import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import type { TeachingSpec } from "@/lib/math/teachingBlock";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

const OBJECT_SIZE = 24;

/**
 * Objects to count for a small whole-number fact. The server sends the numbers
 * and the object; this draws them and never recomputes the fact.
 *
 * add: two groups, then the total. subtract: one row with the taken-away
 * objects crossed out. multiply: rows of objects. divide: equal groups.
 */
export function CountingPicture({ spec }: { spec: TeachingSpec }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const first = Number(spec.first);
  const second = Number(spec.second);
  const result = Number(spec.result);
  const emoji = typeof spec.object === "string" ? spec.object : "●";

  const objects = (count: number, crossedFrom = count) =>
    Array.from({ length: count }, (_, i) =>
      i >= crossedFrom ? (
        <View key={i} style={s.objectCell} testID="counting-crossed">
          <Text style={[s.object, s.faded]}>{emoji}</Text>
          <View style={s.strike} />
        </View>
      ) : (
        <View key={i} style={s.objectCell} testID="counting-object">
          <Text style={s.object}>{emoji}</Text>
        </View>
      ),
    );
  const total = (value: number) => (
    <Text style={s.sign} testID="counting-total">
      = {value}
    </Text>
  );

  if (spec.operation === "add") {
    return (
      <View style={s.line}>
        <View style={s.group}>{objects(first)}</View>
        <Text style={s.sign}>+</Text>
        <View style={s.group}>{objects(second)}</View>
        {total(result)}
      </View>
    );
  }
  if (spec.operation === "subtract") {
    return (
      <View style={s.line}>
        <View style={s.group}>{objects(first, first - second)}</View>
        {total(result)}
      </View>
    );
  }
  if (spec.operation === "multiply") {
    return (
      <View style={s.line}>
        <View style={s.rows}>
          {Array.from({ length: first }, (_, row) => (
            <View key={row} style={s.group} testID="counting-row">
              {objects(second)}
            </View>
          ))}
        </View>
        {total(result)}
      </View>
    );
  }
  return (
    <View style={s.line}>
      {Array.from({ length: second }, (_, group) => (
        <View key={group} style={s.group} testID="counting-group">
          {objects(result)}
        </View>
      ))}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    line: {
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "center",
      gap: Space.sm,
    },
    rows: { gap: Space.xs },
    group: {
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "center",
      gap: Space.xxs,
      paddingVertical: Space.xxs,
      paddingHorizontal: Space.xs,
      borderRadius: Radius.md,
      backgroundColor: t.surfaceAlt,
      maxWidth: "100%",
    },
    objectCell: {
      width: OBJECT_SIZE + 4,
      height: OBJECT_SIZE + 6,
      alignItems: "center",
      justifyContent: "center",
    },
    object: { fontSize: OBJECT_SIZE, lineHeight: OBJECT_SIZE + 6 },
    faded: { opacity: 0.3 },
    strike: {
      position: "absolute",
      width: OBJECT_SIZE + 6,
      height: 2,
      borderRadius: 1,
      backgroundColor: t.textSecondary,
      transform: [{ rotate: "-45deg" }],
    },
    sign: { ...Type.title, ...Weight.semibold, color: t.text },
  });
}
