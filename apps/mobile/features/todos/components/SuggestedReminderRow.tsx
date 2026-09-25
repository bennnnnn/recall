import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { describeDueAt } from "@/features/todos/model/dueDate";
import type { SuggestedReminder } from "@/lib/api";
import { selection, tap } from "@/lib/haptics";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { Radius } from "@/lib/radius";

type Props = {
  reminder: SuggestedReminder;
  busy?: boolean;
  onAdd: () => void;
  onDismiss: () => void;
};

/** A pending Gmail suggestion, kept compact so To-do remains a list rather than a calendar. */
export function SuggestedReminderRow({ reminder, busy, onAdd, onDismiss }: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const dueLabel = reminder.due_at ? describeDueAt(reminder.due_at)?.label : null;

  return (
    <View style={s.row}>
      <View style={s.iconWrap}>
        <Icon name="mail-outline" size={18} color={C.primary} />
      </View>
      <View style={s.body}>
        <Text style={s.title} numberOfLines={2}>{reminder.title}</Text>
        {reminder.source_sender ? (
          <Text style={s.meta} numberOfLines={1}>
            {t("suggested.from_sender", { sender: reminder.source_sender })}
            {dueLabel ? ` · ${dueLabel}` : ""}
          </Text>
        ) : dueLabel ? <Text style={s.meta}>{dueLabel}</Text> : null}
        {reminder.source_snippet ? (
          <Text style={s.snippet} numberOfLines={2}>{reminder.source_snippet}</Text>
        ) : null}
        <View style={s.actions}>
          <Pressable
            style={s.addButton}
            onPress={() => { tap(); onAdd(); }}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel={t("suggested.add")}
            accessibilityState={{ disabled: Boolean(busy), busy: Boolean(busy) }}
          >
            <Text style={s.addText}>{t("suggested.add")}</Text>
          </Pressable>
          <Pressable
            style={s.dismissButton}
            onPress={() => { selection(); onDismiss(); }}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel={t("suggested.dismiss")}
            accessibilityState={{ disabled: Boolean(busy), busy: Boolean(busy) }}
          >
            <Text style={s.dismissText}>{t("suggested.dismiss")}</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    row: {
      flexDirection: "row",
      gap: Space.sm,
      padding: Space.md,
      marginHorizontal: Space.md,
      marginBottom: Space.xs,
      borderRadius: Radius.md,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      backgroundColor: C.surface,
    },
    iconWrap: {
      width: 32,
      height: 32,
      borderRadius: Radius.xl,
      backgroundColor: C.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    body: { flex: 1 },
    title: { ...Type.body, fontWeight: "600", color: C.text },
    meta: { ...Type.compact, color: C.textSecondary, marginTop: 2 },
    snippet: { ...Type.compact, color: C.textSecondary, marginTop: Space.xxs },
    actions: { flexDirection: "row", gap: Space.sm, marginTop: Space.sm },
    addButton: {
      minHeight: 40,
      justifyContent: "center",
      paddingHorizontal: Space.md,
      borderRadius: Radius.sm,
      backgroundColor: C.primary,
    },
    addText: { ...Type.label, color: C.onPrimary },
    dismissButton: {
      minHeight: 40,
      minWidth: 44,
      justifyContent: "center",
      alignItems: "center",
      paddingHorizontal: Space.xs,
    },
    dismissText: { ...Type.secondary, color: C.textSecondary },
  });
}
