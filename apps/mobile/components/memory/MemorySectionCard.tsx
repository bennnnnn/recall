import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { Icon } from "@/components/Icon";
import type { Memory } from "@/lib/api";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";
import { useTheme, type Theme } from "@/lib/theme";

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

type Props = {
  type: string;
  facts: Memory[];
  pending: boolean;
  onEditFact: (fact: Memory) => void;
  onDeleteFact: (fact: Memory) => void;
  onMuteFact: (fact: Memory) => void;
  onDeleteSection: () => void;
};

export function MemorySectionCard({
  type,
  facts,
  pending,
  onEditFact,
  onDeleteFact,
  onMuteFact,
  onDeleteSection,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { t } = useTranslation();

  return (
    <View style={s.group}>
      <View style={s.groupHeader}>
        <Text style={s.groupTitle}>{memoryTypeLabel(type, t)}</Text>
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
      <View style={s.card}>
        {facts.map((fact) => {
          const muted = fact.status === "muted";
          const confirmed = confirmedLabel(fact.last_confirmed_at ?? fact.updated_at);
          return (
            <View key={fact.id} style={s.factRow}>
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
                <Pressable
                  hitSlop={8}
                  onPress={() => onMuteFact(fact)}
                  disabled={pending}
                  accessibilityRole="button"
                  accessibilityLabel={muted ? t("memory.unmute") : t("memory.mute")}
                >
                  <Icon
                    name={muted ? "eye-off-outline" : "eye-outline"}
                    size={18}
                    color={theme.textTertiary}
                  />
                </Pressable>
                <Pressable
                  hitSlop={8}
                  onPress={() => onDeleteFact(fact)}
                  disabled={pending}
                  accessibilityState={{ disabled: pending, busy: pending }}
                  accessibilityRole="button"
                  accessibilityLabel={t("memory.delete_fact_a11y")}
                >
                  <Icon name="close-circle-outline" size={18} danger />
                </Pressable>
              </View>
            </View>
          );
        })}
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
    factMain: { flex: 1 },
    factActions: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
    },
    factText: { flex: 1, ...Type.body, color: theme.text },
    mutedText: { color: theme.textSecondary },
    meta: { ...Type.meta, color: theme.textTertiary, marginTop: 4 },
  });
}
