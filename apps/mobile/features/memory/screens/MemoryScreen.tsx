import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import {
  MemoryFactRow,
  MemoryFold,
  MemorySectionHeader,
} from "@/features/memory/components/MemoryRows";
import { IconButton } from "@/components/IconButton";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useMemoryActions } from "@/features/memory/hooks/useMemoryActions";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { getCachedMemories } from "@/features/memory/model/memoryListCache";
import { MEMORY_TEXT_MAX_LENGTH, stripMemoryAsOf } from "@/features/memory/model/memoryFacts";
import { EditIcon, IconSize } from "@/lib/icons";
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
    pendingTypes,
  } = useMemoryActions(token);
  const [refreshing, setRefreshing] = useState(false);
  const [editingPage, setEditingPage] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
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

  const draftsInvalid = useMemo(() => {
    if (!editingPage) return false;
    return memories.some((fact) => {
      const next = stripMemoryAsOf(drafts[fact.id] ?? fact.text);
      return !next || Array.from(next).length > MEMORY_TEXT_MAX_LENGTH;
    });
  }, [editingPage, memories, drafts]);

  const beginEdit = useCallback(() => {
    if (!isCurrentView() || editBlocked || savingRef.current) return;
    const next: Record<string, string> = {};
    for (const fact of memories) next[fact.id] = stripMemoryAsOf(fact.text);
    setDrafts(next);
    setEditingPage(true);
  }, [isCurrentView, editBlocked, memories]);

  const saveEdit = useCallback(async () => {
    if (!isCurrentView() || savingRef.current || draftsInvalid) return;
    const changes: { id: string; text: string }[] = [];
    for (const fact of memories) {
      const next = stripMemoryAsOf(drafts[fact.id] ?? fact.text);
      if (next !== fact.text) changes.push({ id: fact.id, text: next });
    }
    if (changes.length === 0) {
      setEditingPage(false);
      setDrafts({});
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
    if (!isCurrentView()) return;
    savingRef.current = false;
    setSavingEdit(false);
    setEditingPage(false);
    setDrafts({});
  }, [isCurrentView, draftsInvalid, memories, drafts, updateMemoryText, feedback, t]);

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
          disabled={savingEdit || editBlocked || (editingPage && draftsInvalid)}
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
      <MemoryFold editing={editingPage} fadeColor={theme.surfaceAlt}>
        {sections.map((section, sectionIndex) => {
          const pending = pendingTypes.has(section.type);
          const lastSection = sectionIndex === sections.length - 1;
          return (
            <View key={section.type}>
              <MemorySectionHeader type={section.type} first={sectionIndex === 0} />
              {section.facts.map((fact, index) => {
                const draft = drafts[fact.id] ?? stripMemoryAsOf(fact.text);
                const draftLength = Array.from(stripMemoryAsOf(draft)).length;
                return (
                  <MemoryFactRow
                    key={fact.id}
                    fact={fact}
                    pending={pending}
                    first={index === 0}
                    last={lastSection && index === section.facts.length - 1}
                    editing={editingPage}
                    draftText={draft}
                    draftTooLong={editingPage && draftLength > MEMORY_TEXT_MAX_LENGTH}
                    onChangeDraft={(text) => {
                      setDrafts((prev) => ({ ...prev, [fact.id]: text }));
                    }}
                  />
                );
              })}
            </View>
          );
        })}
      </MemoryFold>
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
  });
}
