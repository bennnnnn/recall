import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { RefreshControl, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import {
  MemoryFactRow,
  MemoryFold,
  MemorySectionHeader,
  memorySectionLabel,
} from "@/features/memory/components/MemoryRows";
import { IconButton } from "@/ui/controls/IconButton";
import { SkeletonList } from "@/ui/feedback/SkeletonLoader";
import { StateView } from "@/ui/feedback/StateView";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useMemoryActions } from "@/features/memory/hooks/useMemoryActions";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { getCachedMemories } from "@/features/memory/model/memoryListCache";
import {
  MEMORY_TEXT_MAX_LENGTH,
  formatMemoryPage,
  parseMemoryPage,
  stripMemoryAsOf,
  visibleMemorySections,
  type MemoryPageLabel,
} from "@/features/memory/model/memoryFacts";
import { MESSAGE_FOLD_MAX_HEIGHT } from "@/lib/markdown/messageFold";
import { EditIcon, IconSize } from "@/lib/icons";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

const TYPE_ORDER = ["profile", "preference", "project", "fact", "focus"];

export default function MemoryScreen() {
  const view = useAccountViewOwner();
  return <MemoryContent key={view.key} isCurrentView={view.isCurrent} />;
}

function MemoryContent({ isCurrentView }: { isCurrentView: () => boolean }) {
  const { token } = useAuth();
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
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
    updateMemoryText,
    deleteFact,
    pendingTypes,
  } = useMemoryActions(token);
  const [refreshing, setRefreshing] = useState(false);
  const [editingPage, setEditingPage] = useState(false);
  const [listExpanded, setListExpanded] = useState(false);
  const [draft, setDraft] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const savingRef = useRef(false);
  const refreshingRef = useRef(false);

  useEffect(() => {
    if (!isCurrentView()) return;
    void load({
      silent: hasLoaded() || Boolean(getCachedMemories()),
      force: false,
    });
  }, [isCurrentView, load, hasLoaded]);

  const sections = useMemo(() => {
    const byType = new Map<string, typeof memories>();
    for (const memory of memories) {
      const list = byType.get(memory.type) ?? [];
      list.push(memory);
      byType.set(memory.type, list);
    }
    return TYPE_ORDER
      .map((type) => ({ type, facts: byType.get(type) ?? [] }))
      .filter((section) => section.facts.length > 0);
  }, [memories]);

  const editBlocked = memories.some((fact) => pendingTypes.has(fact.type));
  const foldedList = useMemo(
    () => visibleMemorySections(sections, MESSAGE_FOLD_MAX_HEIGHT),
    [sections],
  );
  const shownSections = listExpanded ? sections : foldedList.sections;
  const pageLabels = useMemo<MemoryPageLabel[]>(
    () => sections.map((section) => ({ type: section.type, label: memorySectionLabel(section.type, t) })),
    [sections, t],
  );
  const parsedDraft = useMemo(
    () => (editingPage ? parseMemoryPage(draft, pageLabels) : null),
    [editingPage, draft, pageLabels],
  );
  const draftTooLong = useMemo(() => {
    if (!parsedDraft) return false;
    for (const lines of parsedDraft.values()) {
      if (lines.some((line) => Array.from(line).length > MEMORY_TEXT_MAX_LENGTH)) return true;
    }
    return false;
  }, [parsedDraft]);
  const draftEmpty = useMemo(() => {
    if (!parsedDraft) return false;
    for (const lines of parsedDraft.values()) {
      if (lines.length > 0) return false;
    }
    return true;
  }, [parsedDraft]);

  const beginEdit = useCallback(() => {
    if (!isCurrentView() || editBlocked || savingRef.current) return;
    setDraft(formatMemoryPage(sections.map((section) => ({
      label: memorySectionLabel(section.type, t),
      facts: section.facts.map((fact) => stripMemoryAsOf(fact.text)),
    }))));
    setEditingPage(true);
  }, [isCurrentView, editBlocked, sections, t]);

  const saveEdit = useCallback(async () => {
    if (!isCurrentView() || savingRef.current || draftTooLong || draftEmpty || !parsedDraft) return;
    const changes: { id: string; text: string }[] = [];
    const removed: typeof memories = [];
    for (const section of sections) {
      const lines = parsedDraft.get(section.type) ?? [];
      if (lines.length > section.facts.length) {
        reportRecoverableError(feedback, t("memory.edit_failed"));
        return;
      }
      lines.forEach((line, index) => {
        const fact = section.facts[index];
        if (fact && line !== fact.text) changes.push({ id: fact.id, text: line });
      });
      removed.push(...section.facts.slice(lines.length));
    }
    if (changes.length === 0 && removed.length === 0) {
      setEditingPage(false);
      setDraft("");
      return;
    }
    savingRef.current = true;
    setSavingEdit(true);
    for (const change of changes) {
      const ok = await updateMemoryText(change.id, change.text);
      if (!isCurrentView()) return;
      if (!ok) {
        savingRef.current = false;
        setSavingEdit(false);
        reportRecoverableError(feedback, t("memory.edit_failed"));
        return;
      }
    }
    for (const fact of removed) {
      const ok = await deleteFact(fact);
      if (!isCurrentView()) return;
      if (!ok) {
        savingRef.current = false;
        setSavingEdit(false);
        reportRecoverableError(feedback, t("memory.edit_failed"));
        return;
      }
    }
    if (!isCurrentView()) return;
    savingRef.current = false;
    setSavingEdit(false);
    setEditingPage(false);
    setDraft("");
  }, [
    isCurrentView,
    draftTooLong,
    draftEmpty,
    parsedDraft,
    sections,
    updateMemoryText,
    deleteFact,
    feedback,
    t,
  ]);

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
          onRetry={() => { if (isCurrentView()) void load({ force: true }); }}
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
          onRetry={() => { if (isCurrentView()) router.replace("/"); }}
          retryLabel={t("chat.new_chat")}
        />
      </View>
    );
  }

  return (
    <ScrollView
      style={s.root}
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
      keyboardShouldPersistTaps="handled"
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={async () => {
            if (!isCurrentView() || refreshingRef.current) return;
            refreshingRef.current = true;
            setRefreshing(true);
            await load({ silent: true, force: true });
            if (!isCurrentView()) return;
            refreshingRef.current = false;
            setRefreshing(false);
          }}
        />
      }
    >
      <View style={s.headingRow}>
        <Text style={s.heading}>{t("memory.heading")}</Text>
        <IconButton
          name={editingPage ? "checkmark" : undefined}
          icon={
            editingPage ? undefined : (
              <EditIcon size={IconSize.md} color={theme.text} />
            )
          }
          size={IconSize.sm}
          color={theme.accent}
          onPress={() => { if (editingPage) void saveEdit(); else beginEdit(); }}
          disabled={savingEdit || editBlocked || (editingPage && (draftTooLong || draftEmpty))}
          accessibilityLabel={editingPage ? t("common.save") : t("memory.edit_title")}
        />
      </View>
      {error ? (
        <StateView
          variant="error"
          title={t("common.error")}
          onRetry={() => { if (isCurrentView()) void load({ force: true }); }}
          retryLabel={t("common.retry")}
        />
      ) : null}
      {editingPage ? (
        <TextInput
          style={[s.pageEditor, draftTooLong ? s.pageEditorError : null]}
          value={draft}
          onChangeText={setDraft}
          multiline
          editable={!savingEdit}
          textAlignVertical="top"
          accessibilityLabel={t("memory.heading")}
        />
      ) : (
        <MemoryFold
          fadeColor={theme.surfaceAlt}
          overflows={foldedList.overflows}
          expanded={listExpanded}
          onToggle={() => setListExpanded((value) => !value)}
        >
          {shownSections.map((section, sectionIndex) => {
            const lastSection = sectionIndex === shownSections.length - 1;
            return (
              <View key={section.type}>
                <MemorySectionHeader type={section.type} first={sectionIndex === 0} />
                {section.facts.map((fact, index) => (
                  <MemoryFactRow
                    key={fact.id}
                    fact={fact}
                    first={index === 0}
                    last={lastSection && index === section.facts.length - 1}
                  />
                ))}
              </View>
            );
          })}
        </MemoryFold>
      )}
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
    content: { padding: Space.md },
    headingRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: Space.gutter,
    },
    heading: { ...Type.title, color: theme.text, flex: 1 },
    pageEditor: {
      minHeight: 220,
      borderRadius: Radius.lg,
      backgroundColor: theme.surfaceAlt,
      padding: Space.md,
      ...Type.body,
      color: theme.text,
    },
    pageEditorError: {
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.danger,
    },
  });
}
