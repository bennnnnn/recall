import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import type { JobSearchProfile } from "@/lib/api";
import { searchProfileFields } from "@/features/job-search/model/searchFields";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

/**
 * Search-card body: one row per profile field — icon + caption label on the
 * left, value chip(s) on the right — so the card reads as labeled data.
 */
export function SearchProfileFields({ profile }: { profile: JobSearchProfile }) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  return (
    <View style={s.fields}>
      {searchProfileFields(profile, t).map((field) => (
        <View key={field.key} style={s.row}>
          <View style={s.label}>
            <Icon name={field.icon} size={14} color={C.textTertiary} />
            <Text style={s.labelText}>{field.label}</Text>
          </View>
          <View style={s.values}>
            {field.values.map((value) => (
              <View key={value} style={s.chip}>
                <Text style={s.chipText} numberOfLines={1}>
                  {value}
                </Text>
              </View>
            ))}
          </View>
        </View>
      ))}
    </View>
  );
}

const LABEL_WIDTH = 148;

function makeStyles(C: Theme) {
  return StyleSheet.create({
    fields: { gap: Space.xs },
    row: { flexDirection: "row", alignItems: "center", gap: Space.sm },
    label: {
      width: LABEL_WIDTH,
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
    },
    labelText: { ...Type.caption, color: C.textSecondary, flexShrink: 1 },
    values: { flex: 1, flexDirection: "row", flexWrap: "wrap", gap: Space.xxs },
    chip: {
      minHeight: 28,
      justifyContent: "center",
      paddingHorizontal: Space.xs,
      borderRadius: Radius.full,
      backgroundColor: C.surfaceAlt,
      maxWidth: "100%",
    },
    chipText: { ...Type.compact, color: C.text, ...Weight.semibold },
  });
}
