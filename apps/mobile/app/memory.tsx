import { useCallback, useMemo, useRef, useState } from "react";
import {
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Redirect, useFocusEffect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { StateView } from "@/components/StateView";
import { useAuth } from "@/contexts/AuthContext";
import { api, Memory } from "@/lib/api";
import { Theme, useTheme } from "@/lib/theme";

const TYPE_ORDER = ["profile", "preference", "project", "fact", "focus"];
const COLLAPSED_LINES = 3;

function memoryTypeLabel(type: string, t: (key: string) => string): string {
  const key = `memory.type.${type}`;
  const label = t(key);
  return label === key ? type : label;
}

function sectionNeedsCollapse(text: string): boolean {
  return text.trim().length > 120 || text.trim().split(/\n/).length > COLLAPSED_LINES;
}

type MemorySectionCardProps = {
  section: Memory;
  expanded: boolean;
  onToggle: () => void;
  onDelete: () => void;
};

function MemorySectionCard({
  section,
  expanded,
  onToggle,
  onDelete,
  styles: s,
  theme,
}: MemorySectionCardProps & {
  styles: ReturnType<typeof makeStyles>;
  theme: Theme;
}) {
  const { t } = useTranslation();
  const collapsible = sectionNeedsCollapse(section.text);

  return (
    <View style={s.group}>
      <View style={s.groupHeader}>
        <Pressable
          style={s.groupHeaderMain}
          onPress={collapsible ? onToggle : undefined}
          disabled={!collapsible}
        >
          <Text style={s.groupTitle}>{memoryTypeLabel(section.type, t)}</Text>
          {collapsible ? (
            <Ionicons
              name={expanded ? "chevron-up" : "chevron-down"}
              size={18}
              color={theme.textSecondary}
            />
          ) : null}
        </Pressable>
        <Pressable hitSlop={8} onPress={onDelete} accessibilityRole="button">
          <Ionicons name="trash-outline" size={16} color={theme.textTertiary} />
        </Pressable>
      </View>
      <Pressable
        style={s.card}
        onPress={collapsible ? onToggle : undefined}
        disabled={!collapsible}
      >
        <Text
          style={s.cardText}
          numberOfLines={collapsible && !expanded ? COLLAPSED_LINES : undefined}
        >
          {section.text}
        </Text>
        {collapsible ? (
          <Text style={s.expandHint}>
            {expanded ? t("common.show_less") : t("common.show_more")}
          </Text>
        ) : null}
        {section.confidence != null ? (
          <Text style={s.conf}>
            {t("memory.confidence", {
              percent: Math.round(section.confidence * 100),
            })}
          </Text>
        ) : null}
      </Pressable>
    </View>
  );
}

export default function MemoryScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [loading, setLoading] = useState(true);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [error, setError] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set());
  const hasLoadedRef = useRef(false);

  const toggleSection = useCallback((type: string) => {
    setExpandedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }, []);

  const load = useCallback(async (opts?: { silent?: boolean }) => {
    if (!token) {
      setLoading(false);
      return;
    }
    const firstLoad = !hasLoadedRef.current;
    if (!opts?.silent && firstLoad) {
      setLoading(true);
    }
    setError(false);
    try {
      setMemories(await api.listMemories(token));
    } catch {
      setError(true);
    } finally {
      hasLoadedRef.current = true;
      if (!opts?.silent && firstLoad) {
        setLoading(false);
      }
    }
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      void load({ silent: hasLoadedRef.current });
    }, [load]),
  );

  const sections = useMemo(() => {
    const byType = new Map<string, Memory>();
    for (const memory of memories) {
      if (!byType.has(memory.type)) byType.set(memory.type, memory);
    }
    return TYPE_ORDER.map((type) => byType.get(type)).filter(Boolean) as Memory[];
  }, [memories]);

  if (!token) return <Redirect href="/login" />;

  if (loading && memories.length === 0) {
    return (
      <View style={s.center}>
        <StateView variant="loading" />
      </View>
    );
  }

  if (error && memories.length === 0) {
    return (
      <View style={s.center}>
        <StateView
          variant="error"
          title={t("common.error")}
          onRetry={() => void load()}
          retryLabel={t("common.retry")}
        />
      </View>
    );
  }

  if (sections.length === 0) {
    return (
      <View style={s.center}>
        <StateView
          variant="empty"
          icon="sparkles-outline"
          title={t("memory.empty_title")}
          message={t("memory.empty_body")}
        />
      </View>
    );
  }

  return (
    <ScrollView
      style={s.root}
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + 24 }]}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={async () => {
            setRefreshing(true);
            await load({ silent: true });
            setRefreshing(false);
          }}
        />
      }
    >
      <Text style={s.heading}>{t("memory.heading")}</Text>
      <Text style={s.subheading}>{t("memory.section_hint")}</Text>
      {sections.map((section) => (
        <MemorySectionCard
          key={section.type}
          section={section}
          expanded={expandedTypes.has(section.type)}
          onToggle={() => toggleSection(section.type)}
          styles={s}
          theme={theme}
          onDelete={() => {
            if (!token) return;
            Alert.alert(
              t("memory.delete_confirm_title"),
              t("memory.delete_confirm_body"),
              [
                { text: t("common.cancel"), style: "cancel" },
                {
                  text: t("common.delete"),
                  style: "destructive",
                  onPress: async () => {
                    try {
                      await api.deleteMemorySection(token, section.type);
                      setMemories((prev) =>
                        prev.filter((item) => item.type !== section.type),
                      );
                      setExpandedTypes((prev) => {
                        const next = new Set(prev);
                        next.delete(section.type);
                        return next;
                      });
                    } catch {
                      Alert.alert(t("common.error"), t("memory.delete_failed"));
                    }
                  },
                },
              ],
            );
          }}
        />
      ))}
    </ScrollView>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.bg,
  },
  root: { flex: 1, backgroundColor: theme.bg },
  content: { padding: 16 },
  heading: { fontSize: 20, fontWeight: "700", color: theme.text, marginBottom: 6 },
  subheading: {
    fontSize: 14,
    color: theme.textSecondary,
    marginBottom: 20,
    lineHeight: 20,
  },
  group: { marginBottom: 20 },
  groupHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 8,
    gap: 8,
  },
  groupHeaderMain: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  },
  groupTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: theme.text,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  card: {
    backgroundColor: theme.surface,
    borderRadius: 12,
    padding: 14,
  },
  cardText: { fontSize: 15, color: theme.text, lineHeight: 22 },
  expandHint: {
    fontSize: 13,
    fontWeight: "600",
    color: theme.primary,
    marginTop: 8,
  },
  conf: { fontSize: 12, color: theme.textTertiary, marginTop: 8 },
  });
}
