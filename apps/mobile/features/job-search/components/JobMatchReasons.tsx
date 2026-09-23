import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import type { JobMatch } from "@/lib/api";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export function JobMatchReasons({
  match,
  maxReasons,
}: {
  match: JobMatch;
  maxReasons?: number;
}) {
  const C = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(C), [C]);
  const [expanded, setExpanded] = useState(false);
  const reasons = maxReasons == null ? match.match_reasons : match.match_reasons.slice(0, maxReasons);
  if (reasons.length === 0 && !match.gap) return null;

  return (
    <View style={s.block}>
      <Pressable
        style={({ pressed }) => [s.heading, pressed && s.pressed]}
        onPress={(event) => {
          event.stopPropagation();
          setExpanded((value) => !value);
        }}
        accessibilityRole="button"
        accessibilityState={{ expanded }}
        accessibilityLabel={t("my_job.why_matches")}
        accessibilityHint={t(expanded ? "common.show_less" : "common.show_more")}
      >
        <Text style={s.title}>{t("my_job.why_matches")}</Text>
        <Icon
          name={expanded ? "chevron-up" : "chevron-down"}
          size={18}
          color={C.textTertiary}
        />
      </Pressable>

      {expanded ? (
        <View style={s.content} testID="job-match-reasons-content">
          {reasons.map((reason) => (
            <View key={reason} style={s.reasonRow}>
              <View style={s.reasonDot} />
              <Text style={s.reasonText}>{reason}</Text>
            </View>
          ))}
          {match.gap ? (
            <View style={[s.reasonRow, reasons.length > 0 && s.gapRow]}>
              <Icon name="information-circle-outline" size={18} color={C.textTertiary} />
              <Text style={s.gapText}>{match.gap}</Text>
            </View>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    block: {
      backgroundColor: C.contentSurface,
      borderRadius: Radius.xl,
      overflow: "hidden",
    },
    heading: {
      minHeight: 44,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: Space.sm,
      gap: Space.xs,
    },
    title: { ...Type.label, color: C.text, flex: 1 },
    content: { paddingHorizontal: Space.sm, paddingBottom: Space.sm, gap: Space.xs },
    reasonRow: { flexDirection: "row", alignItems: "flex-start", gap: Space.xs },
    reasonDot: {
      width: 6,
      height: 6,
      borderRadius: 3,
      backgroundColor: C.primary,
      marginTop: 7,
    },
    reasonText: { ...Type.secondary, color: C.textSecondary, flex: 1 },
    gapRow: {
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: C.border,
      paddingTop: Space.xs,
      marginTop: 2,
    },
    gapText: { ...Type.compact, color: C.textTertiary, flex: 1 },
    pressed: { opacity: 0.68 },
  });
}
