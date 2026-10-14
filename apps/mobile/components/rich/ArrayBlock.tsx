import { useMemo } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { PARAGRAPH_GAP } from "@/components/markdown/markdownContentStyles";
import { CODE_FONT } from "@/lib/fonts";
import i18n from "@/lib/i18n";
import { isUnfinishedJson } from "@/lib/jsonFence";
import { arrayText, formatCell, parseArrayFence } from "@/lib/lesson/lessonFences";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = { content: string };

/** A list as a row of numbered boxes: each value over its index. */
export function ArrayBlock({ content }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const fence = useMemo(() => parseArrayFence(content), [content]);

  if (!fence) {
    if (isUnfinishedJson(content)) return null;
    return <Text style={s.error}>{i18n.t("rich.array_error")}</Text>;
  }

  return (
    <View
      style={s.wrap}
      accessible
      accessibilityRole="image"
      accessibilityLabel={arrayText(fence)}
      testID="array-block"
    >
      {fence.name ? <Text style={s.name}>{fence.name}</Text> : null}
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View style={s.row}>
          {fence.values.map((value, index) => {
            const lit = fence.highlight.includes(index);
            return (
              <View key={index} style={s.cell}>
                <View style={[s.box, lit && s.boxLit]}>
                  <Text style={[s.value, lit && s.valueLit]} numberOfLines={1}>
                    {formatCell(value)}
                  </Text>
                </View>
                <Text style={s.index}>{i18n.t("rich.array_index", { index })}</Text>
              </View>
            );
          })}
        </View>
      </ScrollView>
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: { marginBottom: PARAGRAPH_GAP, gap: Space.xs },
    name: { ...Type.secondary, fontFamily: CODE_FONT, color: t.textSecondary },
    row: { flexDirection: "row", gap: Space.xs },
    cell: { alignItems: "center", gap: Space.xxs },
    box: {
      minWidth: 56,
      minHeight: 48,
      paddingHorizontal: Space.sm,
      borderRadius: Radius.md,
      borderWidth: 1,
      borderColor: t.border,
      backgroundColor: t.surfaceAlt,
      alignItems: "center",
      justifyContent: "center",
    },
    boxLit: { borderColor: t.primary, backgroundColor: t.primaryLight },
    value: { ...Type.body, fontFamily: CODE_FONT, color: t.text },
    valueLit: { color: t.primary },
    index: { ...Type.caption, color: t.textSecondary },
    error: { ...Type.secondary, color: t.textSecondary, marginBottom: PARAGRAPH_GAP },
  });
}
