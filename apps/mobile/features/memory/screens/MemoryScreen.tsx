import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { RefreshControl, StyleSheet, Text, View } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import {
  MemoryFactRow,
  MemorySectionHeader,
  memoryRowKey,
  type MemoryRow,
} from "@/features/memory/components/MemoryRows";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useMemoryActions } from "@/features/memory/hooks/useMemoryActions";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { Memory } from "@/lib/api";
import { getCachedMemories } from "@/features/memory/model/memoryListCache";
import { MEMORY_TEXT_MAX_LENGTH, stripMemoryAsOf } from "@/features/memory/model/memoryFacts";
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
  const [editing, setEditing] = useState<Memory | null>(null);
  const [draftText, setDraftText] = useState("");
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
    const byType = new Map<string, Memory[]>();
    for (const memory of memories) {
      const list = byType.get(memory.type) ?? [];
      list.push(memory);
      byType.set(memory.type, list);
    }
    return TYPE_ORDER
      .map((type) => ({ type, facts: byType.get(type) ?? [] }))
      .filter((section) => section.facts.length > 0);
  }, [memories]);

  const closeEdit = useCallback(() => {
    if (!isCurrentView() || savingRef.current) return;
    setEditing(null);
    setDraftText("");
  }, [isCurrentView]);

  const saveEdit = useCallback(async () => {
    if (!isCurrentView() || !editing || savingRef.current || pendingTypes.has(editing.type)) return;
    const nextText = stripMemoryAsOf(draftText);
    // The counter + disabled Save already communicate this inline.
    if (!nextText || Array.from(nextText).length > MEMORY_TEXT_MAX_LENGTH) return;
    savingRef.current = true;
    setSavingEdit(true);
    const ok = await updateMemoryText(editing.id, nextText);
    if (!isCurrentView()) return;
    savingRef.current = false;
    setSavingEdit(false);
    if (ok) {
      setEditing(null);
      setDraftText("");
    } else {
      reportRecoverableError(feedback, t("memory.edit_failed"));
    }
  }, [isCurrentView, editing, draftText, updateMemoryText, pendingTypes, feedback, t]);

  const rows = useMemo<MemoryRow[]>(() => {
    const out: MemoryRow[] = [];
    sections.forEach((section, sectionIndex) => {
      const pending = pendingTypes.has(section.type);
      out.push({ kind: "section", type: section.type, first: sectionIndex === 0 });
      section.facts.forEach((fact, index) =>
        out.push({
          kind: "fact",
          fact,
          pending,
          first: index === 0,
          last:
            sectionIndex === sections.length - 1 &&
            index === section.facts.length - 1,
        }),
      );
    });
    return out;
  }, [sections, pendingTypes]);

  const handleEditFact = useCallback(
    (fact: Memory) => {
      if (!isCurrentView() || pendingTypes.has(fact.type)) return;
      setEditing(fact);
      setDraftText(stripMemoryAsOf(fact.text));
    },
    [isCurrentView, pendingTypes],
  );

  const draftLength = useMemo(() => Array.from(stripMemoryAsOf(draftText)).length, [draftText]);
  const draftTooLong = draftLength > MEMORY_TEXT_MAX_LENGTH;

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
      <FlashList
        data={rows}
        keyExtractor={memoryRowKey}
        getItemType={(row) => row.kind}
        style={s.root}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
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
        ListHeaderComponent={
          <View>
            <Text style={s.heading}>{t("memory.heading")}</Text>
            {error ? (
              <StateView
                variant="error"
                title={t("common.error")}
                onRetry={() => { if (isCurrentView()) void load({ force: true }); }}
                retryLabel={t("common.retry")}
              />
            ) : null}
          </View>
        }
        renderItem={({ item }) =>
          item.kind === "section" ? (
            <MemorySectionHeader type={item.type} first={item.first} />
          ) : (
            <MemoryFactRow
              fact={item.fact}
              pending={item.pending}
              first={item.first}
              last={item.last}
              editing={editing?.id === item.fact.id}
              draftText={editing?.id === item.fact.id ? draftText : ""}
              draftTooLong={editing?.id === item.fact.id && draftTooLong}
              saving={editing?.id === item.fact.id && savingEdit}
              onEditFact={handleEditFact}
              onChangeDraft={setDraftText}
              onSaveEdit={() => void saveEdit()}
              onCancelEdit={closeEdit}
            />
          )
        }
      />
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
    heading: { ...Type.title, color: theme.text, marginBottom: Space.gutter },
  });
}
