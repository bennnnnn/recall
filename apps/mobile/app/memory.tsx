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

import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useAuth } from "@/contexts/AuthContext";
import { api, Memory } from "@/lib/api";
import { splitMemoryFacts } from "@/lib/memoryFacts";
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
  onDeleteSection: () => void;
  onDeleteFact: (factIndex: number) => void;
};

function MemorySectionCard({
  section,
  expanded,
  onToggle,
  onDeleteSection,
  onDeleteFact,
  styles: s,
  theme,
}: MemorySectionCardProps & {
  styles: ReturnType<typeof makeStyles>;
  theme: Theme;
}) {
  const { t } = useTranslation();
  const facts = useMemo(() => splitMemoryFacts(section.text), [section.text]);
  const showFacts = facts.length > 1;
  const collapsible = !showFacts && sectionNeedsCollapse(section.text);
  const visibleFacts = expanded || !collapsible ? facts : facts.slice(0, COLLAPSED_LINES);

  return (
    <View style={s.group}>
      <View style={s.groupHeader}>
        <Pressable
          style={s.groupHeaderMain}
          onPress={collapsible || (showFacts && facts.length > COLLAPSED_LINES) ? onToggle : undefined}
          disabled={!collapsible && !(showFacts && facts.length > COLLAPSED_LINES)}
        >
          <Text style={s.groupTitle}>{memoryTypeLabel(section.type, t)}</Text>
          {collapsible || (showFacts && facts.length > COLLAPSED_LINES) ? (
            <Ionicons
              name={expanded ? "chevron-up" : "chevron-down"}
              size={18}
              color={theme.textSecondary}
            />
          ) : null}
        </Pressable>
        <Pressable hitSlop={8} onPress={onDeleteSection} accessibilityRole="button">
          <Ionicons name="trash-outline" size={16} color={theme.textTertiary} />
        </Pressable>
      </View>
      <View style={s.card}>
        {showFacts ? (
          visibleFacts.map((fact, index) => (
            <View key={`${section.id}-${index}`} style={s.factRow}>
              <Text style={s.factText}>{fact}</Text>
              <Pressable
                hitSlop={8}
                onPress={() => onDeleteFact(index)}
                accessibilityRole="button"
                accessibilityLabel={t("memory.delete_fact_a11y")}
              >
                <Ionicons name="close-circle-outline" size={18} color={theme.textTertiary} />
              </Pressable>
            </View>
          ))
        ) : (
          <Pressable
            onPress={collapsible ? onToggle : undefined}
            disabled={!collapsible}
          >
            <Text
              style={s.cardText}
              numberOfLines={collapsible && !expanded ? COLLAPSED_LINES : undefined}
            >
              {section.text}
            </Text>
          </Pressable>
        )}
        {showFacts && facts.length > COLLAPSED_LINES ? (
          <Pressable onPress={onToggle}>
            <Text style={s.expandHint}>
              {expanded ? t("common.show_less") : t("common.show_more")}
            </Text>
          </Pressable>
        ) : collapsible ? (
          <Pressable onPress={onToggle}>
            <Text style={s.expandHint}>
              {expanded ? t("common.show_less") : t("common.show_more")}
            </Text>
          </Pressable>
        ) : null}
        {section.confidence != null ? (
          <Text style={s.conf}>
            {t("memory.confidence", {
              percent: Math.round(section.confidence * 100),
            })}
          </Text>
        ) : null}
      </View>
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
    return <SkeletonList />;
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
          onDeleteSection={() => {
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
                    const snapshot = memories;
                    setMemories((prev) =>
                      prev.filter((item) => item.type !== section.type),
                    );
                    setExpandedTypes((prev) => {
                      const next = new Set(prev);
                      next.delete(section.type);
                      return next;
                    });
                    try {
                      await api.deleteMemorySection(token, section.type);
                    } catch {
                      setMemories(snapshot);
                      Alert.alert(t("common.error"), t("memory.delete_failed"));
                    }
                  },
                },
              ],
            );
          }}
          onDeleteFact={(factIndex) => {
            if (!token) return;
            Alert.alert(
              t("memory.delete_fact_title"),
              t("memory.delete_fact_body"),
              [
                { text: t("common.cancel"), style: "cancel" },
                {
                  text: t("common.delete"),
                  style: "destructive",
                  onPress: async () => {
                    const snapshot = memories;
                    const facts = splitMemoryFacts(section.text);
                    facts.splice(factIndex, 1);
                    if (facts.length === 0) {
                      setMemories((prev) =>
                        prev.filter((item) => item.id !== section.id),
                      );
                    } else {
                      const nextText =
                        facts.join(". ") + (facts.at(-1)?.endsWith(".") ? "" : ".");
                      setMemories((prev) =>
                        prev.map((item) =>
                          item.id === section.id ? { ...item, text: nextText } : item,
                        ),
                      );
                    }
                    try {
                      await api.deleteMemoryFact(token, section.id, factIndex);
                    } catch {
                      setMemories(snapshot);
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
  factRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
    marginBottom: 10,
  },
  factText: { flex: 1, fontSize: 15, color: theme.text, lineHeight: 22 },
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
