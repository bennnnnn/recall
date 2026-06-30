import { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { Theme, useTheme } from "@/lib/theme";
import { api, type ProjectItem, type ProjectPosGroupSummary } from "@/lib/api";
import { statusLabel } from "@/lib/languageLevels";
import { speakWord } from "@/lib/pronunciation";

type Props = {
  token: string;
  projectId: string;
  group: ProjectPosGroupSummary;
  initialItems?: ProjectItem[];
  onSpeechUnavailable?: () => void;
};

function statusIcon(item: ProjectItem): keyof typeof Ionicons.glyphMap {
  if (item.status === "mastered" || item.mastered) return "checkmark-circle";
  if (item.status === "learning") return "ellipse";
  return "ellipse-outline";
}

function statusColor(item: ProjectItem, theme: Theme): string {
  if (item.status === "mastered" || item.mastered) return theme.primary;
  if (item.status === "learning") return "#FF9F0A";
  return theme.textTertiary;
}

export function ProjectPosGroupItems({
  token,
  projectId,
  group,
  initialItems,
  onSpeechUnavailable,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [loading, setLoading] = useState(!initialItems);
  const [items, setItems] = useState<ProjectItem[]>(initialItems ?? []);

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      setItems(
        await api.getProjectPosItems(token, projectId, group.part_of_speech, { limit: 100 }),
      );
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [token, projectId, group.part_of_speech]);

  useEffect(() => {
    if (initialItems) {
      setItems(initialItems);
      setLoading(false);
      return;
    }
    setItems([]);
    void loadItems();
  }, [initialItems, loadItems]);

  if (loading) {
    return <ActivityIndicator color={theme.primary} style={s.loader} />;
  }

  if (items.length === 0) {
    return <Text style={s.empty}>No words in this group.</Text>;
  }

  return (
    <View style={s.items}>
      {items.map((item) => (
        <View key={item.id} style={s.itemRow}>
          <Ionicons name={statusIcon(item)} size={20} color={statusColor(item, theme)} />
          <View style={s.itemMain}>
            <View style={s.itemTop}>
              <Text style={[s.itemContent, item.mastered && s.itemMastered]}>
                {item.content}
              </Text>
              <Pressable
                hitSlop={8}
                onPress={async () => {
                  const result = await speakWord(item.content, {
                    language: "en-US",
                    pronunciationUrl: item.pronunciation_url,
                  });
                  if (!result.ok && result.reason === "unavailable") {
                    onSpeechUnavailable?.();
                  }
                }}
              >
                <Ionicons name="volume-medium-outline" size={18} color={theme.primary} />
              </Pressable>
            </View>
            {item.definition ? <Text style={s.itemDef}>{item.definition}</Text> : null}
            {item.example_sentence ? (
              <Text style={s.itemNote}>"{item.example_sentence}"</Text>
            ) : null}
            <Text style={s.itemMeta}>{statusLabel(item.status)}</Text>
          </View>
        </View>
      ))}
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    loader: { paddingVertical: 16 },
    empty: { fontSize: 14, color: theme.textSecondary, paddingVertical: 8 },
    items: { gap: 10 },
    itemRow: { flexDirection: "row", alignItems: "flex-start", gap: 10 },
    itemMain: { flex: 1, gap: 2 },
    itemTop: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 8,
    },
    itemContent: { fontSize: 16, fontWeight: "700", color: theme.text, flex: 1 },
    itemMastered: { color: theme.textSecondary, textDecorationLine: "line-through" },
    itemDef: { fontSize: 14, color: theme.textSecondary },
    itemNote: { fontSize: 13, lineHeight: 18, color: theme.textSecondary, fontStyle: "italic" },
    itemMeta: { fontSize: 11, fontWeight: "600", color: theme.textTertiary, marginTop: 2 },
  });
}
