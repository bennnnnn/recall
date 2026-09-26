import { View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import { ReminderBadge } from "@/components/ReminderBadge";
import { tap } from "@/lib/haptics";
import { ListRow } from "@/ui/list/ListRow";

import type { ConversationListStyles } from "./conversationListStyles";
import { IconSize } from "@/ui/icons/sizes";

type Props = {
  styles: ConversationListStyles;
  showIndicator: boolean;
  unseenCount: number;
  onMyJob: () => void;
  onProjects: () => void;
  onReminders: () => void;
  onGallery: () => void;
};

export function DrawerNavLinks({
  styles: s,
  showIndicator,
  unseenCount,
  onMyJob,
  onProjects,
  onReminders,
  onGallery,
}: Props) {
  const { t } = useTranslation();

  return (
    <View style={s.drawerNav}>
      <ListRow
        appearance="plain"
        icon="briefcase"
        title={t("drawer.my_job")}
        onPress={() => {
          tap();
          onMyJob();
        }}
        style={s.navRow}
      />
      <ListRow
        appearance="plain"
        icon="graduation-cap"
        title={t("drawer.projects")}
        onPress={() => {
          tap();
          onProjects();
        }}
        style={s.navRow}
      />
      <ListRow
        appearance="plain"
        leading={
          <View style={s.navIconWrap}>
            <Icon name="calendar" size={IconSize.sm} />
            {showIndicator ? <ReminderBadge count={unseenCount} style={s.navBadge} /> : null}
          </View>
        }
        title={t("drawer.reminders")}
        accessibilityLabel={
          showIndicator
            ? t("reminders.badge_accessibility", { count: unseenCount })
            : t("drawer.reminders")
        }
        onPress={() => {
          tap();
          onReminders();
        }}
        style={s.navRow}
      />
      <ListRow
        appearance="plain"
        icon="images"
        title={t("drawer.gallery")}
        onPress={() => {
          tap();
          onGallery();
        }}
        style={s.navRow}
      />
    </View>
  );
}
