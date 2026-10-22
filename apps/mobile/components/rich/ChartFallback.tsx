/**
 * What a chart card shows when its chart cannot be drawn: one line saying so, the
 * chart's data as a small table when it has any, and a way to its source. Never a
 * blank plot or a Vega error message.
 */
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import type { ChartTable } from "@/lib/chartSpec";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";

type Props = {
  table: ChartTable | null;
  /** Null once the source is showing. */
  onShowSource: (() => void) | null;
};

export function ChartFallback({ table, onShowSource }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={s.wrap}>
      <View style={s.note}>
        <Icon name="alert-circle" size={IconSize.sm} color={theme.textSecondary} />
        <Text style={s.noteText}>{t(table ? "rich.chart_data_instead" : "rich.chart_error")}</Text>
      </View>
      {table ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <View style={s.table}>
            {[table.columns, ...table.rows].map((row, r) => (
              <View key={r} style={[s.row, r > 0 && s.rowBorder]}>
                {row.map((value, c) => (
                  <Text key={c} style={[s.cell, r === 0 && s.headerCell]} numberOfLines={1}>
                    {value}
                  </Text>
                ))}
              </View>
            ))}
          </View>
        </ScrollView>
      ) : null}
      {onShowSource ? (
        <Pressable onPress={onShowSource} hitSlop={8} accessibilityRole="button">
          <Text style={s.link}>{t("rich.chart_show_source")}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: { padding: Space.md, gap: Space.sm },
    note: { flexDirection: "row", alignItems: "center", gap: Space.xs },
    noteText: { ...Type.compact, color: t.textSecondary, flexShrink: 1 },
    table: {
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      borderRadius: Radius.xs,
    },
    row: { flexDirection: "row" },
    rowBorder: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: t.border },
    cell: {
      ...Type.meta,
      fontVariant: ["tabular-nums"],
      color: t.text,
      minWidth: 72,
      maxWidth: 160,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xxs,
    },
    headerCell: { ...Weight.semibold, color: t.textSecondary },
    link: { ...Type.compact, color: t.primary },
  });
}
