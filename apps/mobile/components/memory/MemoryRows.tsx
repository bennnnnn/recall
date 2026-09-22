import { useMemo } from "react";
import { StyleSheet, Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";
import { IconButton } from "@/components/IconButton";
import type { Memory } from "@/lib/api";
import { MEMORY_TEXT_MAX_LENGTH } from "@/lib/memoryFacts";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";
import { useTheme, type Theme } from "@/lib/theme";

/** Flattened row model for the Memory screen's sectioned FlashList. */
export type MemoryRow =
  | { kind: "section"; type: string }
  | {
      kind: "fact";
      sectionType: string;
      fact: Memory;
      pending: boolean;
      first: boolean;
      last: boolean;
    };

export function memoryRowKey(row: MemoryRow): string {
  return row.kind === "section" ? `section-${row.type}` : row.fact.id;
}

function memoryTypeLabel(type: string, t: (key: string) => string): string {
  const key = `memory.type.${type}`;
  const label = t(key);
  return label === key ? type : label;
}

/** Sticky section header. Memory deletion belongs in Settings, not this view. */
export function MemorySectionHeader({ type }: { type: string }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { t } = useTranslation();

  return (
    <View style={s.groupHeader}>
      <Text style={s.groupTitle}>{memoryTypeLabel(type, t)}</Text>
    </View>
  );
}

/** One fact inside its section's card run (first/last carry the rounding). */
export function MemoryFactRow({
  fact,
  pending,
  first,
  last,
  editing,
  draftText,
  draftTooLong,
  saving,
  onEditFact,
  onChangeDraft,
  onSaveEdit,
  onCancelEdit,
}: {
  fact: Memory;
  pending: boolean;
  first: boolean;
  last: boolean;
  editing: boolean;
  draftText: string;
  draftTooLong: boolean;
  saving: boolean;
  onEditFact: (fact: Memory) => void;
  onChangeDraft: (text: string) => void;
  onSaveEdit: () => void;
  onCancelEdit: () => void;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { t } = useTranslation();

  return (
    <View
      style={[
        s.factRow,
        first ? s.factRowFirst : null,
        last ? s.factRowLast : null,
        editing ? s.factRowEditing : null,
      ]}
    >
      {editing ? (
        <View style={s.inlineEditor}>
          <TextInput
            style={[s.inlineInput, draftTooLong ? s.inlineInputError : null]}
            accessibilityLabel={t("memory.edit_title")}
            value={draftText}
            onChangeText={onChangeDraft}
            multiline
            editable={!saving}
            autoFocus
            textAlignVertical="top"
          />
          <View style={s.inlineFooter}>
            <Text style={[s.counter, draftTooLong ? s.counterOver : null]}>
              {t("memory.edit_count", {
                count: Array.from(draftText).length,
                max: MEMORY_TEXT_MAX_LENGTH,
              })}
            </Text>
            <View style={s.factActions}>
              <IconButton
                name="close"
                size={20}
                color={theme.textSecondary}
                onPress={onCancelEdit}
                disabled={saving}
                accessibilityLabel={t("common.cancel")}
                style={s.inlineAction}
              />
              <IconButton
                name="checkmark"
                size={20}
                color={theme.accent}
                onPress={onSaveEdit}
                disabled={saving || !draftText.trim() || draftTooLong}
                accessibilityLabel={t("common.save")}
                style={s.inlineAction}
              />
            </View>
          </View>
        </View>
      ) : (
        <>
          <View style={s.factMain}>
            <Text style={s.factText}>{fact.text}</Text>
          </View>
          <View style={s.factActions}>
            <IconButton
              name="pencil-outline"
              size={18}
              color={theme.textSecondary}
              onPress={() => onEditFact(fact)}
              disabled={pending}
              accessibilityLabel={t("memory.edit_fact_a11y")}
              style={s.factAction}
            />
          </View>
        </>
      )}
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    groupHeader: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: Space.xs,
      gap: Space.xs,
      paddingTop: Space.sm,
      // Sticky headers scroll over fact rows — must be opaque.
      backgroundColor: theme.bg,
    },
    groupTitle: {
      ...Type.caption,
      fontWeight: "700",
      color: theme.text,
      textTransform: "uppercase",
      letterSpacing: 0.5,
    },
    factRow: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: 10,
      backgroundColor: theme.surfaceAlt,
      paddingHorizontal: Space.md,
      paddingVertical: 5,
    },
    factRowFirst: {
      borderTopLeftRadius: Radius.lg,
      borderTopRightRadius: Radius.lg,
      paddingTop: Space.md,
    },
    factRowLast: {
      borderBottomLeftRadius: Radius.lg,
      borderBottomRightRadius: Radius.lg,
      paddingBottom: Space.md,
      marginBottom: 20,
    },
    factRowEditing: {
      paddingVertical: Space.sm,
    },
    factMain: { flex: 1 },
    inlineEditor: { flex: 1 },
    inlineInput: {
      minHeight: 76,
      maxHeight: 180,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      borderRadius: Radius.md,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.sm,
      ...Type.body,
      color: theme.text,
      backgroundColor: theme.bg,
    },
    inlineInputError: { borderColor: theme.danger },
    inlineFooter: {
      minHeight: 36,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      marginTop: 2,
    },
    counter: { ...Type.meta, color: theme.textTertiary },
    counterOver: { color: theme.danger },
    factActions: {
      flexDirection: "row",
      alignItems: "center",
    },
    // 44×44 IconButton boxes; negative vertical margin keeps the row height
    // driven by the fact text, not the touch targets.
    factAction: { marginVertical: -12 },
    inlineAction: { marginVertical: -6 },
    factText: { flex: 1, ...Type.body, color: theme.text },
  });
}
