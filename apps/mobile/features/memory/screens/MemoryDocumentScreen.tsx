import { useCallback, useEffect, useMemo, useState } from "react";
import {
  type GestureResponderEvent,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Redirect, useLocalSearchParams, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { SettingsFieldSheet } from "@/components/settings/SettingsFieldSheet";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { MemoryComposer } from "@/features/memory/components/MemoryComposer";
import { useMemoryDocuments } from "@/features/memory/hooks/useMemoryDocuments";
import {
  documentSummary,
  documentTitle,
  parseMemoryDate,
} from "@/features/memory/model/memoryDocuments";
import { MEMORY_TEXT_MAX_LENGTH, stripMemoryAsOf } from "@/features/memory/model/memoryFacts";
import type { Memory } from "@/features/memory/types";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { formatMonthDayYear } from "@/lib/datetime/format";
import { tap } from "@/lib/haptics";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Button } from "@/ui/controls/Button";
import { SkeletonList } from "@/ui/feedback/SkeletonLoader";
import { StateView } from "@/ui/feedback/StateView";
import { confirmDialog } from "@/ui/overlay/dialogs";
import { Menu } from "@/ui/overlay/Menu";

type FactMenu = { fact: Memory; point: { x: number; y: number } };

export default function MemoryDocumentScreen() {
  const view = useAccountViewOwner();
  return <DocumentContent key={view.key} isCurrentView={view.isCurrent} />;
}

function DocumentContent({ isCurrentView }: { isCurrentView: () => boolean }) {
  const { token } = useAuth();
  const { key } = useLocalSearchParams<{ key: string }>();
  const { t, i18n } = useTranslation();
  const locale = i18n?.language;
  const theme = useTheme();
  const router = useRouter();
  const feedback = useActionFeedbackOptional();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const memory = useMemoryDocuments(token);
  const { load, instruct, deleteDocument, deleteFact, editFact } = memory;
  const document = memory.documents.find((doc) => doc.key === key);
  const [menu, setMenu] = useState<FactMenu | null>(null);
  const [editing, setEditing] = useState<{ fact: Memory; text: string } | null>(null);
  const [saving, setSaving] = useState(false);

  // Opened from a link, the pages may not be loaded yet.
  const missing = !document;
  useEffect(() => {
    if (missing && isCurrentView()) void load();
  }, [missing, isCurrentView, load]);

  const title = document ? documentTitle(document, t) : "";
  const summary = document ? documentSummary(document, t) : "";
  const updated = parseMemoryDate(document?.updated_at);

  const openMenu = useCallback((fact: Memory, event: GestureResponderEvent) => {
    tap();
    setMenu({ fact, point: { x: event.nativeEvent.pageX, y: event.nativeEvent.pageY } });
  }, []);

  const removeDocument = useCallback(() => {
    if (!document) return;
    void confirmDialog({
      title: t("memory.delete_document_title", { title }),
      message: t("memory.delete_document_body"),
      confirmLabel: t("common.delete"),
      destructive: true,
    }).then(async (ok) => {
      if (!ok) return;
      const done = await deleteDocument(document.key);
      if (!isCurrentView()) return;
      if (!done) {
        reportRecoverableError(feedback, t("memory.delete_failed"));
        return;
      }
      router.back();
    });
  }, [document, t, title, deleteDocument, isCurrentView, feedback, router]);

  const removeFact = useCallback((fact: Memory) => {
    const lastFact = document?.facts.length === 1;
    void confirmDialog({
      title: t("memory.delete_fact_title"),
      message: stripMemoryAsOf(fact.text),
      confirmLabel: t("common.delete"),
      destructive: true,
    }).then(async (ok) => {
      if (!ok) return;
      const done = await deleteFact(fact.id);
      if (!isCurrentView()) return;
      if (!done) {
        reportRecoverableError(feedback, t("memory.delete_failed"));
        return;
      }
      // The page is gone with its last fact.
      if (lastFact) router.back();
    });
  }, [document, t, deleteFact, isCurrentView, feedback, router]);

  const saveEdit = useCallback(async () => {
    const text = editing?.text.trim();
    if (!editing || !text || saving) return;
    setSaving(true);
    const ok = await editFact(editing.fact.id, text);
    if (!isCurrentView()) return;
    setSaving(false);
    if (!ok) {
      reportRecoverableError(feedback, t("memory.edit_failed"));
      return;
    }
    setEditing(null);
  }, [editing, saving, editFact, isCurrentView, feedback, t]);

  const submit = useCallback(async (instruction: string) => {
    const outcome = await instruct(instruction, typeof key === "string" ? key : undefined);
    if (!isCurrentView()) return false;
    if (!outcome.ok) {
      reportRecoverableError(feedback, t("memory.instruct_failed"));
      return false;
    }
    feedback?.success(outcome.reply || t("memory.instruct_done"));
    return true;
  }, [instruct, key, isCurrentView, feedback, t]);

  if (!token) return <Redirect href="/login" />;
  if (!document) {
    if (memory.loading) return <SkeletonList />;
    return (
      <View style={s.center}>
        <StateView
          variant="empty"
          icon="sparkles"
          title={t("memory.document_gone")}
          onRetry={() => router.back()}
          retryLabel={t("memory.back_to_memory")}
        />
      </View>
    );
  }

  return (
    <View style={s.root}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={s.content}
        keyboardShouldPersistTaps="handled"
        testID="memory-document"
      >
        <View style={s.titleRow}>
          <Text style={s.title} accessibilityRole="header">{title}</Text>
          <Button
            title={t("common.delete")}
            variant="outline"
            size="sm"
            onPress={removeDocument}
            testID="memory-document-delete"
          />
        </View>
        {updated ? (
          <View style={s.block}>
            <Text style={s.label}>{t("memory.last_updated")}</Text>
            <Text style={s.value}>{formatMonthDayYear(updated, locale)}</Text>
          </View>
        ) : null}
        {summary ? (
          <View style={s.block}>
            <Text style={s.label}>{t("memory.summary_label")}</Text>
            <Text style={s.value}>{summary}</Text>
          </View>
        ) : null}
        <View style={s.block}>
          <Text style={s.label}>{t("memory.details_label")}</Text>
          {document.facts.map((fact) => (
            <Pressable
              key={fact.id}
              style={({ pressed }) => [s.fact, pressed && s.factPressed]}
              onPress={(event) => openMenu(fact, event)}
              onLongPress={(event) => openMenu(fact, event)}
              accessibilityRole="button"
              accessibilityLabel={stripMemoryAsOf(fact.text)}
              accessibilityHint={t("memory.fact_hint")}
              testID={`memory-fact-${fact.id}`}
            >
              <Text style={s.bullet}>•</Text>
              <Text style={s.factText}>{stripMemoryAsOf(fact.text)}</Text>
            </Pressable>
          ))}
        </View>
      </ScrollView>
      <MemoryComposer
        placeholder={t("memory.composer_placeholder_document")}
        onSubmit={submit}
      />
      <Menu
        visible={menu != null}
        anchorPoint={menu?.point ?? null}
        onClose={() => setMenu(null)}
        items={[
          {
            key: "edit",
            label: t("memory.edit_fact"),
            icon: "pencil",
            onPress: () => {
              const fact = menu?.fact;
              setMenu(null);
              if (fact) setEditing({ fact, text: stripMemoryAsOf(fact.text) });
            },
          },
          {
            key: "delete",
            label: t("common.delete"),
            icon: "trash",
            destructive: true,
            onPress: () => {
              const fact = menu?.fact;
              setMenu(null);
              if (fact) removeFact(fact);
            },
          },
        ]}
        testID="memory-fact-menu"
      />
      <SettingsFieldSheet
        visible={editing != null}
        title={t("memory.edit_title")}
        value={editing?.text ?? ""}
        onChangeText={(text) => setEditing((current) => (current ? { ...current, text } : current))}
        onClose={() => { if (!saving) setEditing(null); }}
        onSave={() => void saveEdit()}
        multiline
        maxLength={MEMORY_TEXT_MAX_LENGTH}
        saving={saving}
      />
    </View>
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
    scroll: { flex: 1 },
    content: { padding: Space.md, paddingBottom: Space.lg, gap: Space.lg },
    titleRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
    },
    title: { ...Type.title, color: theme.text, flex: 1 },
    block: { gap: Space.xxs },
    label: { ...Type.label, color: theme.textSecondary },
    value: { ...Type.body, color: theme.text },
    fact: {
      flexDirection: "row",
      gap: Space.xs,
      paddingVertical: Space.xxs,
      paddingHorizontal: Space.xxs,
      marginHorizontal: -Space.xxs,
      borderRadius: Radius.md,
    },
    factPressed: { backgroundColor: theme.pressed },
    bullet: { ...Type.body, ...Weight.semibold, color: theme.textSecondary },
    factText: { ...Type.body, color: theme.text, flex: 1 },
  });
}
