import { Pressable, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import type { Theme } from "@/lib/theme";
import type { ConversationListStyles } from "./conversationListStyles";

type Props = {
  styles: ConversationListStyles;
  theme: Theme;
  paddingBottom: number;
  selectedCount: number;
  onArchive: () => void;
  onDelete: () => void;
};

export function DrawerSelectionBar({
  styles: s,
  theme,
  paddingBottom,
  selectedCount,
  onArchive,
  onDelete,
}: Props) {
  const { t } = useTranslation();
  const disabled = selectedCount === 0;

  return (
    <View style={[s.selectionBar, { paddingBottom }]} pointerEvents="box-none">
      <Pressable
        style={[s.selectionAction, disabled && s.selectionActionDisabled]}
        disabled={disabled}
        onPress={onArchive}
      >
        <Ionicons
          name="archive-outline"
          size={18}
          color={disabled ? theme.textTertiary : theme.primary}
        />
        <Text style={[s.selectionActionText, disabled && s.selectionActionTextDisabled]}>
          {t("drawer.bulk_archive")}
        </Text>
      </Pressable>
      <Pressable
        style={[s.selectionAction, disabled && s.selectionActionDisabled]}
        disabled={disabled}
        onPress={onDelete}
      >
        <Ionicons
          name="trash-outline"
          size={18}
          color={disabled ? theme.textTertiary : theme.danger}
        />
        <Text
          style={[
            s.selectionActionText,
            s.selectionActionTextDanger,
            disabled && s.selectionActionTextDisabled,
          ]}
        >
          {t("drawer.bulk_delete")}
        </Text>
      </Pressable>
    </View>
  );
}
