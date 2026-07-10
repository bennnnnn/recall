import { useMemo } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { TRIVIA_TOPICS, type TriviaTopicId } from "@/lib/triviaTopics";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  visible: boolean;
  selected: TriviaTopicId[];
  saving?: boolean;
  onClose: () => void;
  onDone: () => void;
  onToggle: (id: TriviaTopicId) => void;
};

export function TriviaTopicsPickerModal({
  visible,
  selected,
  saving = false,
  onClose,
  onDone,
  onToggle,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const canSave = selected.length > 0 && !saving;

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <View style={[s.root, { paddingTop: insets.top }]}>
        <View style={s.header}>
          <Pressable style={s.headerSide} onPress={onClose} hitSlop={8}>
            <Ionicons name="close" size={26} color={theme.textSecondary} />
          </Pressable>
          <Text style={s.headerTitle}>{t("projects.trivia.topics_picker_title")}</Text>
          <Pressable
            style={s.headerSide}
            onPress={onDone}
            disabled={!canSave}
            hitSlop={8}
          >
            <Text style={[s.done, !canSave && s.doneDisabled]}>{t("common.done")}</Text>
          </Pressable>
        </View>
        <ScrollView contentContainerStyle={[s.content, { paddingBottom: insets.bottom + 24 }]}>
          <Text style={s.hint}>{t("projects.trivia.topics_hint")}</Text>
          <View style={s.list}>
            {TRIVIA_TOPICS.map((topic) => {
              const isSelected = selected.includes(topic.id);
              return (
                <Pressable
                  key={topic.id}
                  style={[s.row, isSelected && s.rowActive]}
                  onPress={() => onToggle(topic.id)}
                >
                  <Text style={[s.rowText, isSelected && s.rowTextActive]}>{t(topic.labelKey)}</Text>
                  {isSelected ? <Ionicons name="checkmark" size={18} color={theme.primary} /> : null}
                </Pressable>
              );
            })}
          </View>
        </ScrollView>
      </View>
    </Modal>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: theme.bg },
    header: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: 12,
      paddingVertical: 10,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: theme.border,
    },
    headerSide: { width: 56, alignItems: "center", justifyContent: "center" },
    headerTitle: {
      flex: 1,
      textAlign: "center",
      fontSize: 17,
      fontWeight: "700",
      color: theme.text,
    },
    done: { fontSize: 16, fontWeight: "700", color: theme.primary },
    doneDisabled: { opacity: 0.4 },
    content: { padding: 16 },
    hint: { fontSize: 14, color: theme.textSecondary, marginBottom: 12 },
    list: { gap: 8 },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      paddingVertical: 14,
      paddingHorizontal: 12,
      borderRadius: 14,
      backgroundColor: theme.surface,
      borderWidth: 1,
      borderColor: theme.border,
    },
    rowActive: {
      borderColor: theme.primary,
      backgroundColor: theme.primaryLight,
    },
    rowText: { flex: 1, fontSize: 16, fontWeight: "600", color: theme.text },
    rowTextActive: { color: theme.primaryDark },
  });
}
