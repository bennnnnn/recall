import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";
import type { SuggestedReminder } from "@/lib/api";
import { describeDueAt } from "@/lib/dueDate";

type Props = {
  reminder: SuggestedReminder;
  busy?: boolean;
  onAdd: () => void;
  onDismiss: () => void;
};

export function SuggestedReminderRow({ reminder, busy, onAdd, onDismiss }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const dueLabel = reminder.due_at ? describeDueAt(reminder.due_at)?.label : null;

  return (
    <View style={s.row}>
      <View style={s.iconWrap}>
        <Ionicons name="mail-outline" size={18} color={theme.primary} />
      </View>
      <View style={s.body}>
        <Text style={s.title} numberOfLines={2}>
          {reminder.title}
        </Text>
        {dueLabel ? <Text style={s.meta}>{dueLabel}</Text> : null}
        {reminder.source_snippet ? (
          <Text style={s.snippet} numberOfLines={2}>
            {reminder.source_snippet}
          </Text>
        ) : null}
        <View style={s.actions}>
          <Pressable style={s.addBtn} onPress={onAdd} disabled={busy}>
            <Text style={s.addText}>{t("suggested.add")}</Text>
          </Pressable>
          <Pressable style={s.dismissBtn} onPress={onDismiss} disabled={busy}>
            <Text style={s.dismissText}>{t("suggested.dismiss")}</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    row: {
      flexDirection: "row",
      gap: 12,
      paddingVertical: 12,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: theme.border,
    },
    iconWrap: {
      width: 32,
      height: 32,
      borderRadius: 16,
      backgroundColor: theme.primaryLight,
      alignItems: "center",
      justifyContent: "center",
      marginTop: 2,
    },
    body: { flex: 1 },
    title: { fontSize: 16, fontWeight: "600", color: theme.text },
    meta: { fontSize: 13, color: theme.textSecondary, marginTop: 2 },
    snippet: { fontSize: 13, color: theme.textSecondary, marginTop: 4 },
    actions: { flexDirection: "row", gap: 12, marginTop: 10 },
    addBtn: {
      paddingHorizontal: 14,
      paddingVertical: 6,
      borderRadius: 8,
      backgroundColor: theme.primary,
    },
    addText: { color: "#fff", fontWeight: "600", fontSize: 14 },
    dismissBtn: { paddingHorizontal: 4, paddingVertical: 6, justifyContent: "center" },
    dismissText: { color: theme.textSecondary, fontSize: 14 },
  });
}
