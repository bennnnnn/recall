import { useMemo } from "react";
import { ActivityIndicator, Alert, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import type { ProjectItem, VocabStatus } from "@/lib/api";
import { speakWord } from "@/lib/pronunciation";
import { useAuth } from "@/contexts/AuthContext";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  item: ProjectItem;
  busy?: boolean;
  showSpeech?: boolean;
  onStatusChange?: (status: VocabStatus) => void | Promise<void>;
  onSpeechUnavailable?: () => void;
};

function statusIcon(item: ProjectItem): keyof typeof Ionicons.glyphMap {
  if (item.status === "mastered" || item.mastered) return "checkmark-circle";
  if (item.status === "learning") return "ellipse";
  return "ellipse-outline";
}

function statusColor(item: ProjectItem, theme: Theme): string {
  if (item.status === "mastered" || item.mastered) return theme.primary;
  // Failed / learning and new — gray (same as daily Failed metric)
  return theme.textTertiary;
}

export function ProjectItemRow({
  item,
  busy = false,
  showSpeech = true,
  onStatusChange,
  onSpeechUnavailable,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const { token } = useAuth();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const mastered = item.status === "mastered" || item.mastered;

  const openStatusMenu = () => {
    if (!onStatusChange || busy) return;
    Alert.alert(item.content, t("projects.status_menu_hint"), [
      {
        text: t("projects.status_new"),
        onPress: () => void onStatusChange("new"),
      },
      {
        text: t("projects.status_missed"),
        onPress: () => void onStatusChange("learning"),
      },
      {
        text: t("projects.status_mastered"),
        onPress: () => void onStatusChange("mastered"),
      },
      { text: t("common.cancel"), style: "cancel" },
    ]);
  };

  return (
    <View style={s.row}>
      <Pressable
        hitSlop={8}
        disabled={!onStatusChange || busy}
        onPress={openStatusMenu}
        onLongPress={openStatusMenu}
        accessibilityRole="button"
        accessibilityLabel={t("projects.status_menu_a11y", { word: item.content })}
      >
        {busy ? (
          <ActivityIndicator size="small" color={theme.primary} />
        ) : (
          <Ionicons name={statusIcon(item)} size={22} color={statusColor(item, theme)} />
        )}
      </Pressable>
      <View style={s.main}>
        <View style={s.top}>
          <Text style={[s.content, mastered && s.contentMastered]} numberOfLines={2}>
            {item.content}
          </Text>
          {showSpeech ? (
            <Pressable
              hitSlop={14}
              onPress={async () => {
                const result = await speakWord(item.content, {
                  language: "en-US",
                  pronunciationUrl: item.pronunciation_url,
                  token,
                });
                if (!result.ok && result.reason === "unavailable") {
                  onSpeechUnavailable?.();
                }
              }}
              accessibilityRole="button"
              accessibilityLabel={t("chat.read_aloud_a11y")}
            >
              <Ionicons name="volume-medium-outline" size={18} color={theme.primary} />
            </Pressable>
          ) : null}
        </View>
        {item.definition ? <Text style={s.def}>{item.definition}</Text> : null}
        {item.example_sentence ? (
          <Text style={s.note}>"{item.example_sentence}"</Text>
        ) : null}
        <Pressable
          disabled={!onStatusChange || busy}
          onPress={openStatusMenu}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel={t("projects.status_menu_a11y", { word: item.content })}
        >
          <View style={[s.statusChip, mastered && s.statusChipMastered]}>
            <Text style={[s.statusChipText, mastered && s.statusChipTextMastered]}>
              {item.status === "learning"
                ? item.last_incorrect_at
                  ? t("projects.status_missed")
                  : t("projects.status_learning")
                : item.status === "mastered" || item.mastered
                  ? t("projects.status_mastered")
                  : t("projects.status_new")}
            </Text>
            {onStatusChange ? (
              <Ionicons name="chevron-down" size={12} color={theme.textTertiary} />
            ) : null}
          </View>
        </Pressable>
      </View>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    row: { flexDirection: "row", alignItems: "flex-start", gap: 10 },
    main: { flex: 1, gap: 4 },
    top: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 8,
    },
    content: { fontSize: 16, fontWeight: "700", color: theme.text, flex: 1 },
    contentMastered: { color: theme.textSecondary, textDecorationLine: "line-through" },
    def: { fontSize: 14, lineHeight: 20, color: theme.textSecondary },
    note: { fontSize: 13, lineHeight: 18, color: theme.textSecondary, fontStyle: "italic" },
    statusChip: {
      alignSelf: "flex-start",
      flexDirection: "row",
      alignItems: "center",
      gap: 4,
      marginTop: 2,
      paddingHorizontal: 8,
      paddingVertical: 4,
      borderRadius: 999,
      backgroundColor: theme.bg,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    statusChipMastered: {
      backgroundColor: theme.primaryLight,
      borderColor: theme.primaryLight,
    },
    statusChipText: { fontSize: 11, fontWeight: "700", color: theme.textSecondary },
    statusChipTextMastered: { color: theme.primary },
  });
}
