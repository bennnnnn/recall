import { useCallback, useEffect, useState } from "react";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { api, SuggestedReminder } from "@/lib/api";
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
  const s = makeStyles(theme);
  const [reminders, setReminders] = useState<SuggestedReminder[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  const load = useCallback(async () => {
    if (!token) {
      setReminders([]);
      return;
    }
    try {
      const data = await api.listSuggestedReminders(token);
      setReminders(data.reminders.slice(0, 3));
    } catch {
      setReminders([]);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  if (reminders.length === 0) return null;

  const handleAdd = async (id: string) => {
    if (!token || busyId) return;
    setBusyId(id);
    try {
      await api.addSuggestedReminder(token, id);
      setReminders((prev) => prev.filter((r) => r.id !== id));
      onAdded?.();
    } catch {
      Alert.alert(t("common.error"), t("reminders.add_failed"));
    } finally {
      setBusyId(null);
    }
  };

  const handleDismiss = async (id: string) => {
    if (!token || busyId) return;
    setBusyId(id);
    try {
      await api.dismissSuggestedReminder(token, id);
      setReminders((prev) => prev.filter((r) => r.id !== id));
      onDismiss?.(id);
    } catch {
      Alert.alert(t("common.error"), t("reminders.dismiss_failed"));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <View style={s.wrap}>
      <Pressable style={s.header} onPress={() => setCollapsed((v) => !v)}>
        <Ionicons name="mail-unread-outline" size={18} color={theme.primary} />
        <Text style={s.headerText}>
          {t("chat.email_suggestions", { count: reminders.length })}
        </Text>
        <Ionicons
          name={collapsed ? "chevron-down" : "chevron-up"}
          size={16}
          color={theme.textTertiary}
        />
      </Pressable>
      {!collapsed ? (
        <View style={s.body}>
          {reminders.map((item) => (
            <View key={item.id} style={s.row}>
              <View style={s.rowBody}>
                <Text style={s.title} numberOfLines={1}>
                  {item.title}
                </Text>
                {item.source_snippet ? (
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
              <Pressable
                hitSlop={8}
                disabled={busyId === item.id}
                onPress={() => void handleDismiss(item.id)}
              >
                <Ionicons name="close" size={18} color={theme.textTertiary} />
              </Pressable>
            </View>
          ))}
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
