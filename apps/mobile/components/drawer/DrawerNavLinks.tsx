import { Pressable, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { ReminderBadge } from "@/components/ReminderBadge";
import type { Theme } from "@/lib/theme";

import type { ConversationListStyles } from "./conversationListStyles";

type Props = {
  styles: ConversationListStyles;
  theme: Theme;
  showIndicator: boolean;
  unseenCount: number;
  onProjects: () => void;
  onLists: () => void;
  onReminders: () => void;
};

export function DrawerNavLinks({
  styles: s,
  theme,
  showIndicator,
  unseenCount,
  onProjects,
  onLists,
  onReminders,
}: Props) {
  const { t } = useTranslation();

  return (
    <View style={s.drawerNav}>
      <Pressable style={s.todosLink} onPress={onProjects}>
        <Ionicons name="school-outline" size={18} color={theme.primary} />
        <Text style={s.todosLinkText}>{t("drawer.projects")}</Text>
        <Ionicons
          name="chevron-forward"
          size={16}
          color={theme.textTertiary}
          style={s.todosChevron}
        />
      </Pressable>

      <Pressable style={s.todosLink} onPress={onLists}>
        <Ionicons name="list-outline" size={18} color={theme.primary} />
        <Text style={s.todosLinkText}>{t("drawer.lists")}</Text>
        <Ionicons
          name="chevron-forward"
          size={16}
          color={theme.textTertiary}
          style={s.todosChevron}
        />
      </Pressable>

      <Pressable style={s.todosLink} onPress={onReminders}>
        <View style={s.navIconWrap}>
          <Ionicons
            name={showIndicator ? "notifications" : "notifications-outline"}
            size={18}
            color={theme.primary}
          />
          {showIndicator ? (
            <ReminderBadge count={unseenCount} style={s.navBadge} />
          ) : null}
        </View>
        <Text style={s.todosLinkText}>{t("drawer.reminders")}</Text>
        <Ionicons
          name="chevron-forward"
          size={16}
          color={theme.textTertiary}
          style={s.todosChevron}
        />
      </Pressable>
    </View>
  );
}
