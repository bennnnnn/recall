import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import type { GoogleCalendarEvent } from "@/lib/api";
import { formatCalendarEventTime } from "@/lib/reminderCalendar";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  event: GoogleCalendarEvent;
};

export function CalendarMeetingRow({ event }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const when = formatCalendarEventTime(event);

  return (
    <View style={s.row}>
      <View style={s.iconWrap}>
        <Ionicons name="calendar" size={18} color="#4285F4" />
      </View>
      <View style={s.main}>
        <Text style={s.title} numberOfLines={2}>
          {event.title}
        </Text>
        <Text style={s.when}>{when}</Text>
        {event.location ? (
          <Text style={s.location} numberOfLines={1}>
            {event.location}
          </Text>
        ) : null}
        <Text style={s.badge}>
          {event.calendar_name
            ? t("calendar.google_meeting_from", { calendar: event.calendar_name })
            : t("calendar.google_meeting")}
        </Text>
      </View>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    row: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: 12,
      paddingVertical: 12,
      paddingHorizontal: 14,
      borderRadius: 14,
      backgroundColor: theme.isDark ? theme.surface : "#F8F9FF",
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      marginBottom: 8,
    },
    iconWrap: {
      width: 28,
      alignItems: "center",
      paddingTop: 2,
    },
    main: { flex: 1, gap: 2 },
    title: { fontSize: 16, fontWeight: "600", color: theme.text },
    when: { fontSize: 13, fontWeight: "600", color: theme.primary },
    location: { fontSize: 13, color: theme.textSecondary },
    badge: {
      fontSize: 11,
      fontWeight: "600",
      color: theme.textTertiary,
      marginTop: 4,
      textTransform: "uppercase",
      letterSpacing: 0.4,
    },
  });
}
