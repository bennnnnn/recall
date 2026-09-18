import { Pressable, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { ReminderBadge } from "@/components/ReminderBadge";
import { tap } from "@/lib/haptics";
import type { Theme } from "@/lib/theme";

import type { ConversationListStyles } from "./conversationListStyles";

type Props = {
  styles: ConversationListStyles;
  theme: Theme;
  showIndicator: boolean;
  unseenCount: number;
  onProjects: () => void;
  onReminders: () => void;
  onAutomations: () => void;
  onGallery: () => void;
};

export function DrawerNavLinks({
  styles: s,
  theme,
  showIndicator,
  unseenCount,
  onProjects,
  onReminders,
  onAutomations,
  onGallery,
}: Props) {
  const { t } = useTranslation();

  return (
    <View style={s.drawerNav}>
      <Pressable
        style={s.todosLink}
        onPress={() => {
          tap();
          onProjects();
        }}
        accessibilityRole="button"
        accessibilityLabel={t("drawer.projects")}
      >
        <Icon name="school-outline" size={18} />
        <Text style={s.todosLinkText}>{t("drawer.projects")}</Text>
        <Icon name="chevron-forward" size={16} color={theme.textTertiary} style={s.todosChevron} />
      </Pressable>

      <Pressable
        style={s.todosLink}
        onPress={() => {
          tap();
          onReminders();
        }}
        accessibilityRole="button"
        accessibilityLabel={
          showIndicator
            ? t("reminders.badge_accessibility", { count: unseenCount })
            : t("drawer.reminders")
        }
      >
        <View style={s.navIconWrap}>
          <Icon name="calendar-outline" size={18} />
          {showIndicator ? (
            <ReminderBadge count={unseenCount} style={s.navBadge} />
          ) : null}
        </View>
        <Text style={s.todosLinkText}>{t("drawer.reminders")}</Text>
        <Icon name="chevron-forward" size={16} color={theme.textTertiary} style={s.todosChevron} />
      </Pressable>

      <Pressable
        style={s.todosLink}
        onPress={() => {
          tap();
          onAutomations();
        }}
        accessibilityRole="button"
        accessibilityLabel={t("drawer.automations")}
      >
        <Icon name="briefcase-outline" size={18} />
        <Text style={s.todosLinkText}>{t("drawer.automations")}</Text>
        <Icon name="chevron-forward" size={16} color={theme.textTertiary} style={s.todosChevron} />
      </Pressable>

      <Pressable
        style={s.todosLink}
        onPress={() => {
          tap();
          onGallery();
        }}
        accessibilityRole="button"
        accessibilityLabel={t("drawer.gallery")}
      >
        <Icon name="library-outline" size={18} />
        <Text style={s.todosLinkText}>{t("drawer.gallery")}</Text>
        <Icon name="chevron-forward" size={16} color={theme.textTertiary} style={s.todosChevron} />
      </Pressable>
    </View>
  );
}
