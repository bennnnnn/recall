import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/components/Icon";
import { IconButton } from "@/components/IconButton";
import { useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { useSuggestedReminders } from "@/hooks/useSuggestedReminders";
import { describeDueAt } from "@/lib/todos/dueDate";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  token: string | null;
  onDismiss?: (id: string) => void;
  onAdded?: () => void;
};

export function SuggestedRemindersNudge({ token, onDismiss, onAdded }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const router = useRouter();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { reminders, busyId, add, dismiss } = useSuggestedReminders(token, {
    onAdded,
    onDismiss,
    refreshOnFocus: false,
  });
  const [collapsed, setCollapsed] = useState(false);

  if (reminders.length === 0) return null;

  const handleAdd = async (id: string) => {
    if (!token || busyId) return;
    await add(id);
  };

  const handleDismiss = async (id: string) => {
    if (!token || busyId) return;
    await dismiss(id);
  };

  return (
    <View style={s.wrap}>
      <Pressable style={s.header} onPress={() => setCollapsed((v) => !v)}>
        <Icon name="mail-unread-outline" size={18} color={theme.primary} />
        <Text style={s.headerText}>
          {t("chat.email_suggestions", { count: reminders.length })}
        </Text>
        <Icon
          name={collapsed ? "chevron-down" : "chevron-up"}
          size={16}
          color={theme.textTertiary}
        />
      </Pressable>
      {!collapsed ? (
        <View style={s.body}>
          {reminders.map((item) => {
            const dueLabel = item.due_at ? describeDueAt(item.due_at)?.label : null;
            const fromLabel = item.source_sender
              ? t("suggested.from_sender", { sender: item.source_sender })
              : null;
            const meta = [fromLabel, dueLabel].filter(Boolean).join(" · ");
            return (
            <View key={item.id} style={s.row}>
              <View style={s.rowBody}>
                <Text style={s.title} numberOfLines={1}>
                  {item.title}
                </Text>
                {meta ? (
                  <Text style={s.meta} numberOfLines={1}>
                    {meta}
                  </Text>
                ) : item.source_snippet ? (
                  <Text style={s.snippet} numberOfLines={1}>
                    {item.source_snippet}
                  </Text>
                ) : null}
              </View>
              <Pressable
                style={s.addBtn}
                disabled={busyId === item.id}
                onPress={() => void handleAdd(item.id)}
              >
                <Text style={s.addText}>{t("reminders.add")}</Text>
              </Pressable>
              <IconButton
                name="close"
                size={18}
                color={theme.textTertiary}
                disabled={busyId === item.id}
                onPress={() => void handleDismiss(item.id)}
                accessibilityLabel={t("common.close")}
              />
            </View>
            );
          })}
          <Pressable style={s.viewAll} onPress={() => router.push("/todos")}>
            <Text style={s.viewAllText}>{t("chat.email_suggestions_view_all")}</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: {
      marginHorizontal: 12,
      marginBottom: 8,
      borderRadius: 14,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      backgroundColor: t.surface,
      overflow: "hidden",
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      paddingHorizontal: 12,
      paddingVertical: 10,
    },
    headerText: { flex: 1, fontSize: 14, fontWeight: "600", color: t.text },
    body: { paddingHorizontal: 12, paddingBottom: 10, gap: 8 },
    row: { flexDirection: "row", alignItems: "center", gap: 8 },
    rowBody: { flex: 1 },
    title: { fontSize: 14, fontWeight: "600", color: t.text },
    meta: { fontSize: 12, color: t.textSecondary, marginTop: 2 },
    snippet: { fontSize: 12, color: t.textTertiary, marginTop: 2 },
    addBtn: {
      paddingHorizontal: 10,
      paddingVertical: 6,
      borderRadius: 8,
      backgroundColor: t.primaryLight,
    },
    addText: { fontSize: 13, fontWeight: "600", color: t.primary },
    viewAll: { alignSelf: "flex-start", paddingVertical: 4 },
    viewAllText: { fontSize: 13, fontWeight: "600", color: t.primary },
  });
}
