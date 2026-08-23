import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { AppSheet } from "@/components/AppSheet";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useAuth } from "@/contexts/AuthContext";
import { useMemoryActions } from "@/hooks/useMemoryActions";
import { Memory } from "@/lib/api";
import { getCachedMemories } from "@/lib/cache/memoryListCache";
import { splitMemoryFacts } from "@/lib/memoryFacts";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

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
  onEditSection: () => void;
  onDeleteSection: () => void;
  onDeleteFact: (factIndex: number, factText: string) => void;
};

function MemorySectionCard({
  section,
  expanded,
  onToggle,
  onEditSection,
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
            <Icon
              name={expanded ? "chevron-up" : "chevron-down"}
              size={18}
              color={theme.textSecondary}
            />
          ) : null}
        </Pressable>
        <View style={s.groupHeaderActions}>
          <Pressable
            hitSlop={14}
            onPress={onEditSection}
            accessibilityRole="button"
            accessibilityLabel={t("memory.edit_section_a11y")}
          >
            <Icon name="create-outline" size={16} color={theme.textTertiary} />
          </Pressable>
          <Pressable
            hitSlop={14}
            onPress={onDeleteSection}
            accessibilityRole="button"
            accessibilityLabel={t("memory.delete_section_a11y")}
          >
            <Icon name="trash-outline" size={16} danger />
          </Pressable>
        </View>
      </View>
      <View style={s.card}>
        {showFacts ? (
          visibleFacts.map((fact, index) => (
            <View key={`${section.id}-${index}`} style={s.factRow}>
              <Text style={s.factText}>{fact}</Text>
              <Pressable
                hitSlop={8}
                onPress={() => onDeleteFact(index, fact)}
                accessibilityRole="button"
                accessibilityLabel={t("memory.delete_fact_a11y")}
              >
                <Icon name="close-circle-outline" size={18} danger />
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
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const {
    memories,
    loading,
    error,
    load,
    hasLoaded,
    deleteSection,
    deleteFact,
    updateMemoryText,
  } = useMemoryActions(token);
  const [refreshing, setRefreshing] = useState(false);
  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState<Memory | null>(null);
  const [draftText, setDraftText] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);

  const toggleSection = useCallback((type: string) => {
    setExpandedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load({
        silent: hasLoaded() || Boolean(getCachedMemories()),
        force: false,
      });
    }, [load, hasLoaded]),
  );

  const sections = useMemo(() => {
    const byType = new Map<string, Memory>();
    for (const memory of memories) {
      if (!byType.has(memory.type)) byType.set(memory.type, memory);
    }
    return TYPE_ORDER.map((type) => byType.get(type)).filter(Boolean) as Memory[];
  }, [memories]);

  const closeEdit = useCallback(() => {
    if (savingEdit) return;
    setEditing(null);
    setDraftText("");
  }, [savingEdit]);

  const saveEdit = useCallback(async () => {
    if (!editing) return;
    const nextText = draftText.trim();
    if (!nextText) {
      Alert.alert(t("common.error"), t("memory.edit_failed"));
      return;
    }
    setSavingEdit(true);
    const ok = await updateMemoryText(editing.id, nextText);
    setSavingEdit(false);
    if (ok) {
      setEditing(null);
      setDraftText("");
    } else {
      Alert.alert(t("common.error"), t("memory.edit_failed"));
    }
  }, [editing, draftText, updateMemoryText, t]);

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
          onRetry={() => router.replace("/")}
          retryLabel={t("chat.new_chat")}
        />
      </View>
    );
  }

  return (
    <>
      <ScrollView
        style={s.root}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={async () => {
              setRefreshing(true);
              await load({ silent: true, force: true });
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
            onEditSection={() => {
              setEditing(section);
              setDraftText(section.text);
            }}
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
                      setExpandedTypes((prev) => {
                        const next = new Set(prev);
                        next.delete(section.type);
                        return next;
                      });
                      if (!(await deleteSection(section.type))) {
                        Alert.alert(t("common.error"), t("memory.delete_failed"));
                      }
                    },
                  },
                ],
              );
            }}
            onDeleteFact={(factIndex, factText) => {
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
                      if (!(await deleteFact(section, factIndex, factText))) {
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

      <AppSheet
        visible={editing != null}
        onClose={closeEdit}
        variant="bottom"
        keyboardAvoiding
        backdropDismiss={!savingEdit}
      >
        <Text style={s.editTitle}>{t("memory.edit_title")}</Text>
        <Text style={s.editHint}>{t("memory.edit_hint")}</Text>
        <TextInput
          style={s.editInput}
          value={draftText}
          onChangeText={setDraftText}
          multiline
          editable={!savingEdit}
          autoFocus
          textAlignVertical="top"
        />
        <View style={s.editActions}>
          <Pressable style={s.editCancel} onPress={closeEdit} disabled={savingEdit}>
            <Text style={s.editCancelText}>{t("common.cancel")}</Text>
          </Pressable>
          <Pressable
            style={[s.editSave, savingEdit && s.editSaveDisabled]}
            onPress={() => void saveEdit()}
            disabled={savingEdit}
          >
            {savingEdit ? (
              <ActivityIndicator color={theme.onPrimary} />
            ) : (
              <Text style={s.editSaveText}>{t("common.save")}</Text>
            )}
          </Pressable>
        </View>
      </AppSheet>
    </>
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
  content: { padding: Space.md },
  heading: { ...Type.title, color: theme.text, marginBottom: Space.xs },
  subheading: {
    ...Type.label,
    fontWeight: "400",
    color: theme.textSecondary,
    marginBottom: 20,
    lineHeight: 20,
  },
  group: { marginBottom: 20 },
  groupHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: Space.xs,
    gap: Space.xs,
  },
  groupHeaderMain: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: Space.xs,
  },
  groupHeaderActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: Space.sm,
  },
  groupTitle: {
    ...Type.caption,
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
  factText: { flex: 1, ...Type.secondary, color: theme.text },
  cardText: { ...Type.secondary, color: theme.text },
  expandHint: {
    ...Type.caption,
    color: theme.primary,
    marginTop: Space.xs,
  },
  conf: { ...Type.meta, color: theme.textTertiary, marginTop: Space.xs },
  editTitle: {
    ...Type.title,
    fontSize: 18,
    color: theme.text,
    marginBottom: Space.xs,
  },
  editHint: {
    ...Type.label,
    fontWeight: "400",
    color: theme.textSecondary,
    lineHeight: 20,
    marginBottom: Space.sm,
  },
  editInput: {
    minHeight: 140,
    maxHeight: 240,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: theme.border,
    borderRadius: 12,
    padding: Space.sm,
    ...Type.secondary,
    color: theme.text,
    backgroundColor: theme.bg,
    marginBottom: Space.md,
  },
  editActions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 10,
  },
  editCancel: {
    paddingHorizontal: Space.md,
    paddingVertical: Space.sm,
    borderRadius: 10,
  },
  editCancelText: {
    ...Type.secondary,
    fontWeight: "600",
    color: theme.textSecondary,
  },
  editSave: {
    minWidth: 96,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: Space.md,
    paddingVertical: Space.sm,
    borderRadius: 10,
    backgroundColor: theme.primary,
  },
  editSaveDisabled: { opacity: 0.7 },
  editSaveText: {
    ...Type.secondary,
    fontWeight: "700",
    color: theme.onPrimary,
  },
  });
}
