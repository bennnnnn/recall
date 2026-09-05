import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { Icon } from "@/components/Icon";
import type { Memory } from "@/lib/api";
import { splitMemoryFacts } from "@/lib/memoryFacts";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";
import { useTheme, type Theme } from "@/lib/theme";

const COLLAPSED_LINES = 3;

function memoryTypeLabel(type: string, t: (key: string) => string): string {
  const key = `memory.type.${type}`;
  const label = t(key);
  return label === key ? type : label;
}

function sectionNeedsCollapse(text: string): boolean {
  return text.trim().length > 120 || text.trim().split(/\n/).length > COLLAPSED_LINES;
}

type Props = {
  section: Memory;
  pending: boolean;
  expanded: boolean;
  onToggle: () => void;
  onEditSection: () => void;
  onDeleteSection: () => void;
  onDeleteFact: (factIndex: number, factText: string) => void;
};

export function MemorySectionCard({
  section,
  pending,
  expanded,
  onToggle,
  onEditSection,
  onDeleteSection,
  onDeleteFact,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { t } = useTranslation();
  const facts = useMemo(() => splitMemoryFacts(section.text), [section.text]);
  const showFacts = facts.length > 1;
  const collapsible = !showFacts && sectionNeedsCollapse(section.text);
  const visibleFacts = expanded ? facts : facts.slice(0, COLLAPSED_LINES);

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
            disabled={pending}
            accessibilityState={{ disabled: pending, busy: pending }}
            accessibilityRole="button"
            accessibilityLabel={t("memory.edit_section_a11y")}
          >
            <Icon name="create-outline" size={16} color={theme.textTertiary} />
          </Pressable>
          <Pressable
            hitSlop={14}
            onPress={onDeleteSection}
            disabled={pending}
            accessibilityState={{ disabled: pending, busy: pending }}
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
                disabled={pending}
                accessibilityState={{ disabled: pending, busy: pending }}
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

function makeStyles(theme: Theme) {
  return StyleSheet.create({
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
      backgroundColor: theme.surfaceAlt,
      borderRadius: Radius.lg,
      padding: Space.md,
    },
    factRow: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: 10,
      marginBottom: 10,
    },
    factText: { flex: 1, ...Type.body, color: theme.text },
    cardText: { ...Type.secondary, color: theme.text },
    expandHint: {
      ...Type.caption,
      color: theme.primary,
      marginTop: Space.xs,
    },
    conf: { ...Type.meta, color: theme.textTertiary, marginTop: Space.xs },
  });
}
