import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export type CalendarNudge = { title: string; startAt: string };

/** Event context carried by a calendar push; shown only after that push is opened. */
export function CalendarNudgeCard({ event }: { event: CalendarNudge }) {
  const { t, i18n } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const start = new Date(event.startAt);
  const when = Number.isFinite(start.getTime())
    ? start.toLocaleString(i18n.language, {
        weekday: "short",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      })
    : null;

  return (
    <View style={s.card} accessibilityRole="summary">
      <View style={s.iconWrap}>
        <Icon name="calendar-outline" size={20} color={C.primary} />
      </View>
      <View style={s.body}>
        <Text style={s.eyebrow}>{t("calendar.google_meeting")}</Text>
        <Text style={s.title} numberOfLines={2}>{event.title}</Text>
        {when ? <Text style={s.time}>{when}</Text> : null}
      </View>
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    card: {
      flexDirection: "row",
      gap: Space.sm,
      marginHorizontal: Space.md,
      marginTop: Space.sm,
      padding: Space.md,
      borderRadius: Radius.md,
      backgroundColor: C.primaryLight,
    },
    iconWrap: {
      width: 38,
      height: 38,
      borderRadius: 19,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.surface,
    },
    body: { flex: 1, gap: 2 },
    eyebrow: { ...Type.caption, fontWeight: "700", color: C.primary },
    title: { ...Type.body, fontWeight: "700", color: C.text },
    time: { ...Type.secondary, color: C.textSecondary },
  });
}
