import { useMemo } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { PARAGRAPH_GAP } from "@/components/markdown/markdownContentStyles";
import i18n from "@/lib/i18n";
import { isUnfinishedJson } from "@/lib/jsonFence";
import {
  arrayText,
  formatCell,
  parseArrayFence,
} from "@/lib/lesson/lessonFences";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

type Props = { content: string };

// Up to this many boxes share the card's width; more scroll sideways.
const FIT_CELLS = 6;

/** A list as boxes, each value over its index, with the pair that matters lit. */
export function ArrayBlock({ content }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const fence = useMemo(() => parseArrayFence(content), [content]);

  if (!fence) {
    if (isUnfinishedJson(content)) return null;
    return <Text style={s.error}>{i18n.t("rich.array_error")}</Text>;
  }

  const fits = fence.values.length <= FIT_CELLS;
  const cells = fence.values.map((value, index) => {
    const lit = fence.highlight.includes(index);
    return (
      <View
        key={index}
        style={[s.cell, fits ? s.cellFit : s.cellFixed, lit && s.cellLit]}
      >
        <Text
          style={[s.value, lit && s.lit]}
          numberOfLines={1}
          adjustsFontSizeToFit
        >
          {formatCell(value)}
        </Text>
        <Text style={[s.index, lit && s.lit]} numberOfLines={1}>
          {i18n.t("rich.array_index", { index })}
        </Text>
      </View>
    );
  });

  return (
    <View
      style={s.card}
      accessible
      accessibilityRole="image"
      accessibilityLabel={arrayText(fence)}
      testID="array-block"
    >
      {fits ? (
        <View style={s.row}>{cells}</View>
      ) : (
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <View style={s.row}>{cells}</View>
        </ScrollView>
      )}
      {fence.caption ? <Text style={s.caption}>{fence.caption}</Text> : null}
      {fence.note ? <Text style={s.note}>{fence.note}</Text> : null}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    card: {
      marginBottom: PARAGRAPH_GAP,
      padding: Space.sm,
      gap: Space.sm,
      borderRadius: Radius.menu,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      backgroundColor: t.bg,
    },
    row: { flexDirection: "row", gap: Space.xs },
    cell: {
      alignItems: "center",
      justifyContent: "center",
      gap: Space.xxs,
      paddingVertical: Space.sm,
      paddingHorizontal: Space.xxs,
      borderRadius: Radius.xl,
    },
    cellFit: { flex: 1, minWidth: 0 },
    cellFixed: { width: 72 },
    cellLit: { backgroundColor: t.successLight },
    value: { ...Type.title, ...Weight.bold, color: t.text },
    index: { ...Type.caption, color: t.textSecondary },
    lit: { color: t.success },
    caption: { ...Type.h3, ...Weight.bold, color: t.text, textAlign: "center" },
    note: { ...Type.secondary, color: t.textSecondary, textAlign: "center" },
    error: {
      ...Type.secondary,
      color: t.textSecondary,
      marginBottom: PARAGRAPH_GAP,
    },
  });
}
