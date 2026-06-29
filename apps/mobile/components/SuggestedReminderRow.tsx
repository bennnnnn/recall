import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { C } from "@/constants/Colors";
import type { SuggestedReminder } from "@/lib/api";
import { describeDueAt } from "@/lib/dueDate";

type Props = {
  reminder: SuggestedReminder;
  busy?: boolean;
  onAdd: () => void;
  onDismiss: () => void;
};

export function SuggestedReminderRow({ reminder, busy, onAdd, onDismiss }: Props) {
  const dueLabel = reminder.due_at ? describeDueAt(reminder.due_at)?.label : null;

  return (
    <View style={s.row}>
      <View style={s.iconWrap}>
        <Ionicons name="mail-outline" size={18} color={C.primary} />
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
            <Text style={s.addText}>Add</Text>
          </Pressable>
          <Pressable style={s.dismissBtn} onPress={onDismiss} disabled={busy}>
            <Text style={s.dismissText}>Dismiss</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  row: {
    flexDirection: "row",
    gap: 12,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
  },
  iconWrap: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: C.primaryLight,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 2,
  },
  body: { flex: 1 },
  title: { fontSize: 16, fontWeight: "600", color: C.text },
  meta: { fontSize: 13, color: C.textSecondary, marginTop: 2 },
  snippet: { fontSize: 13, color: C.textSecondary, marginTop: 4 },
  actions: { flexDirection: "row", gap: 12, marginTop: 10 },
  addBtn: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: C.primary,
  },
  addText: { color: "#fff", fontWeight: "600", fontSize: 14 },
  dismissBtn: { paddingHorizontal: 4, paddingVertical: 6, justifyContent: "center" },
  dismissText: { color: C.textSecondary, fontSize: 14 },
});
