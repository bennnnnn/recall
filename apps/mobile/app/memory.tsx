import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { MemorySectionCard } from "@/components/memory/MemorySectionCard";
import { AppSheet } from "@/components/AppSheet";
import { SheetFormHeader } from "@/components/SheetFormHeader";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useMemoryActions } from "@/hooks/useMemoryActions";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { Memory } from "@/lib/api";
import { getCachedMemories } from "@/lib/cache/memoryListCache";
import { MEMORY_TEXT_MAX_LENGTH, stripMemoryAsOf } from "@/lib/memoryFacts";
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
    deleteSection,
    deleteFact,
    updateMemoryText,
    pendingTypes,
  } = useMemoryActions(token);
  const [refreshing, setRefreshing] = useState(false);
  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState<Memory | null>(null);
  const [draftText, setDraftText] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const savingRef = useRef(false);
  const refreshingRef = useRef(false);

  const toggleSection = useCallback((type: string) => {
    setExpandedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }, []);

  useEffect(() => {
    if (!isCurrentView()) return;
    void load({
      silent: hasLoaded() || Boolean(getCachedMemories()),
      force: false,
    });
  }, [isCurrentView, load, hasLoaded]);

  const sections = useMemo(() => {
    const byType = new Map<string, Memory>();
    for (const memory of memories) {
      if (!byType.has(memory.type)) byType.set(memory.type, memory);
    }
    return TYPE_ORDER.map((type) => byType.get(type)).filter(Boolean) as Memory[];
  }, [memories]);

  const closeEdit = useCallback(() => {
    if (!isCurrentView() || savingRef.current) return;
    setEditing(null);
    setDraftText("");
  }, [isCurrentView]);

  const saveEdit = useCallback(async () => {
    if (!isCurrentView() || !editing || savingRef.current || pendingTypes.has(editing.type)) return;
    const nextText = stripMemoryAsOf(draftText);
    if (!nextText || Array.from(nextText).length > MEMORY_TEXT_MAX_LENGTH) {
      Alert.alert(t("common.error"), t("memory.edit_failed"));
      return;
    }
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
      Alert.alert(t("common.error"), t("memory.edit_failed"));
    }
  }, [isCurrentView, editing, draftText, updateMemoryText, pendingTypes, t]);

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
    <>
      <ScrollView
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
      >
        <Text style={s.heading}>{t("memory.heading")}</Text>
        <Text style={s.subheading}>{t("memory.section_hint")}</Text>
        {error ? <StateView
          variant="error"
          title={t("common.error")}
          onRetry={() => { if (isCurrentView()) void load({ force: true }); }}
          retryLabel={t("common.retry")}
        /> : null}
        {sections.map((section) => (
          <MemorySectionCard
            key={section.type}
            section={section}
            pending={pendingTypes.has(section.type)}
            expanded={expandedTypes.has(section.type)}
            onToggle={() => toggleSection(section.type)}
            onEditSection={() => {
              if (!isCurrentView() || pendingTypes.has(section.type)) return;
              setEditing(section);
              setDraftText(stripMemoryAsOf(section.text));
            }}
            onDeleteSection={() => {
              if (!token || !isCurrentView()) return;
              Alert.alert(
                t("memory.delete_confirm_title"),
                t("memory.delete_confirm_body"),
                [
                  { text: t("common.cancel"), style: "cancel" },
                  {
                    text: t("common.delete"),
                    style: "destructive",
                    onPress: async () => {
                      if (!isCurrentView()) return;
                      setExpandedTypes((prev) => {
                        const next = new Set(prev);
                        next.delete(section.type);
                        return next;
                      });
                      const ok = await deleteSection(section.type);
                      if (isCurrentView() && !ok) {
                        reportRecoverableError(feedback, t("memory.delete_failed"));
                      }
                    },
                  },
                ],
              );
            }}
            onDeleteFact={(factIndex, factText) => {
              if (!token || !isCurrentView()) return;
              Alert.alert(
                t("memory.delete_fact_title"),
                t("memory.delete_fact_body"),
                [
                  { text: t("common.cancel"), style: "cancel" },
                  {
                    text: t("common.delete"),
                    style: "destructive",
                    onPress: async () => {
                      if (!isCurrentView()) return;
                      const ok = await deleteFact(section, factIndex, factText);
                      if (isCurrentView() && !ok) {
                        reportRecoverableError(feedback, t("memory.delete_failed"));
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
        withHandle={false}
        backdropDismiss={!savingEdit}
        contentContainerStyle={s.editSheet}
      >
        <SheetFormHeader
          title={t("memory.edit_title")}
          onCancel={closeEdit}
          onSave={() => void saveEdit()}
          cancelLabel={t("common.cancel")}
          saveLabel={t("common.save")}
          saving={savingEdit}
          saveDisabled={!stripMemoryAsOf(draftText) || Array.from(stripMemoryAsOf(draftText)).length > MEMORY_TEXT_MAX_LENGTH}
        />
        <View style={s.editBody}>
          <Text style={s.editHint}>{t("memory.edit_hint")}</Text>
          <TextInput
            style={s.editInput}
            accessibilityLabel={t("memory.edit_title")}
            value={draftText}
            onChangeText={setDraftText}
            multiline
            editable={!savingEdit}
            autoFocus
            textAlignVertical="top"
          />
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
    editSheet: {
      paddingHorizontal: 0,
      paddingTop: 0,
    },
    editBody: { padding: Space.md },
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
    },
  });
}
