import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Redirect, useFocusEffect } from "expo-router";
import { useTranslation } from "react-i18next";

import { C } from "@/constants/Colors";
import { useAuth } from "@/contexts/AuthContext";
import { api, Memory } from "@/lib/api";

const TYPE_LABEL: Record<string, string> = {
  profile: "👤 Profile",
  preference: "⭐ Preferences",
  project: "🗂 Projects",
  fact: "📌 Facts",
  focus: "🎯 Focus",
};
const TYPE_ORDER = ["profile", "preference", "project", "fact", "focus"];

function groupByType(memories: Memory[]) {
  const g: Record<string, Memory[]> = {};
  for (const m of memories) {
    if (!g[m.type]) g[m.type] = [];
    g[m.type].push(m);
  }
  return g;
}

export default function MemoryScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [memories, setMemories] = useState<Memory[]>([]);

  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(false);
    try {
      setMemories(await api.listMemories(token));
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  if (!token) return <Redirect href="/login" />;

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator color={C.primary} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={s.empty}>
        <Ionicons
          name="cloud-offline-outline"
          size={48}
          color={C.textTertiary}
          style={s.emptyIcon}
        />
        <Text style={s.emptyTitle}>{t("common.error")}</Text>
        <Pressable style={s.retryBtn} onPress={() => load()}>
          <Text style={s.retryText}>{t("common.retry")}</Text>
        </Pressable>
      </View>
    );
  }

  if (memories.length === 0) {
    return (
      <View style={s.empty}>
        <Ionicons
          name="sparkles-outline"
          size={48}
          color={C.primary}
          style={s.emptyIcon}
        />
        <Text style={s.emptyTitle}>{t("memory.empty_title")}</Text>
        <Text style={s.emptyBody}>{t("memory.empty_body")}</Text>
      </View>
    );
  }

  const groups = useMemo(() => groupByType(memories), [memories]);

  return (
    <ScrollView style={s.root} contentContainerStyle={s.content}>
      <Text style={s.heading}>{t("memory.heading")}</Text>
      {TYPE_ORDER.filter((t) => groups[t]?.length).map((type) => (
        <View key={type} style={s.group}>
          <Text style={s.groupTitle}>{TYPE_LABEL[type] ?? type}</Text>
          {groups[type].map((m) => (
            <View key={m.id} style={s.card}>
              <View style={s.cardMain}>
                <Text style={s.cardText}>{m.text}</Text>
                {m.confidence != null && (
                  <Text style={s.conf}>
                    {Math.round(m.confidence * 100)}% confident
                  </Text>
                )}
              </View>
              <Pressable
                hitSlop={8}
                onPress={async () => {
                  if (!token) return;
                  await api.deleteMemory(token, m.id);
                  setMemories((prev) => prev.filter((x) => x.id !== m.id));
                }}
              >
                <Ionicons
                  name="trash-outline"
                  size={16}
                  color={C.textTertiary}
                />
              </Pressable>
            </View>
          ))}
        </View>
      ))}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: C.bg,
  },
  empty: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 32,
    backgroundColor: C.bg,
  },
  emptyIcon: { opacity: 0.5, marginBottom: 16 },
  emptyTitle: { fontSize: 18, fontWeight: "600", color: C.text },
  emptyBody: {
    fontSize: 15,
    color: C.textSecondary,
    marginTop: 6,
    textAlign: "center",
  },
  root: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16 },
  heading: { fontSize: 20, fontWeight: "700", color: C.text, marginBottom: 20 },
  group: { marginBottom: 24 },
  groupTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: C.text,
    marginBottom: 8,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  card: {
    flexDirection: "row",
    alignItems: "flex-start",
    backgroundColor: C.surface,
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
    gap: 8,
  },
  cardMain: { flex: 1 },
  cardText: { fontSize: 15, color: C.text, lineHeight: 21 },
  conf: { fontSize: 12, color: C.textTertiary, marginTop: 4 },
  del: { color: C.textTertiary, fontSize: 16, fontWeight: "700", marginTop: 2 },
  retryBtn: {
    marginTop: 16,
    paddingHorizontal: 20,
    paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: C.primary,
  },
  retryText: { fontSize: 14, fontWeight: "600", color: "#fff" },
});
