import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { IconButton } from "@/components/IconButton";
import type { Memory } from "@/lib/api";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";
import { useTheme, type Theme } from "@/lib/theme";

/** Flattened row model for the Memory screen's sectioned FlashList. */
export type MemoryRow =
  | { kind: "section"; type: string; pending: boolean }
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

function confirmedLabel(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const day = iso.slice(0, 10);
  return day || null;
}

/** Sticky section header (type label + delete-section action). */
export function MemorySectionHeader({
  type,
  pending,
  onDeleteSection,
}: {
  type: string;
  pending: boolean;
  onDeleteSection: (type: string) => void;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { t } = useTranslation();

  return (
    <View style={s.groupHeader}>
      <Text style={s.groupTitle}>{memoryTypeLabel(type, t)}</Text>
      <IconButton
        name="trash-outline"
        size={16}
        color={theme.danger}
        onPress={() => onDeleteSection(type)}
        disabled={pending}
        accessibilityLabel={t("memory.delete_section_a11y")}
        style={s.headerAction}
      />
    </View>
  );
}

/** One fact inside its section's card run (first/last carry the rounding). */
export function MemoryFactRow({
  fact,
  pending,
  first,
  last,
  onEditFact,
  onDeleteFact,
  onMuteFact,
}: {
  fact: Memory;
  pending: boolean;
  first: boolean;
  last: boolean;
  onEditFact: (fact: Memory) => void;
  onDeleteFact: (fact: Memory) => void;
  onMuteFact: (fact: Memory) => void;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { t } = useTranslation();

  const muted = fact.status === "muted";
  const confirmed = confirmedLabel(fact.last_confirmed_at ?? fact.updated_at);
  return (
    <View style={[s.factRow, first ? s.factRowFirst : null, last ? s.factRowLast : null]}>
      <Pressable
        style={s.factMain}
        onPress={() => onEditFact(fact)}
        disabled={pending}
        accessibilityRole="button"
        accessibilityLabel={t("memory.edit_fact_a11y")}
      >
        <Text style={[s.factText, muted ? s.mutedText : null]}>{fact.text}</Text>
        {confirmed ? (
          <Text style={s.meta}>{t("memory.last_confirmed", { date: confirmed })}</Text>
        ) : null}
        {fact.source_chat_title ? (
          <Text style={s.meta}>
            {t("memory.source_chat", { title: fact.source_chat_title })}
          </Text>
        ) : null}
        {muted ? <Text style={s.meta}>{t("memory.muted")}</Text> : null}
      </Pressable>
      <View style={s.factActions}>
        <IconButton
          name={muted ? "eye-off-outline" : "eye-outline"}
          size={18}
          color={theme.textTertiary}
          onPress={() => onMuteFact(fact)}
          disabled={pending}
          accessibilityLabel={muted ? t("memory.unmute") : t("memory.mute")}
          style={s.factAction}
        />
        <IconButton
          name="close-circle-outline"
          size={18}
          color={theme.danger}
          onPress={() => onDeleteFact(fact)}
          disabled={pending}
          accessibilityLabel={t("memory.delete_fact_a11y")}
          style={s.factAction}
        />
      </View>
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
    factMain: { flex: 1 },
    factActions: {
      flexDirection: "row",
      alignItems: "center",
    },
    // 44×44 IconButton boxes; negative vertical margin keeps the row height
    // driven by the fact text, not the touch targets.
    factAction: { marginVertical: -12 },
    headerAction: { marginVertical: -12, marginRight: -12 },
    factText: { flex: 1, ...Type.body, color: theme.text },
    mutedText: { color: theme.textSecondary },
    meta: { ...Type.meta, color: theme.textTertiary, marginTop: 4 },
  });
}
