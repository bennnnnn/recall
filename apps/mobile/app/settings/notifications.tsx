import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, ScrollView, View } from "react-native";
import { Redirect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { SettingsPickerModal } from "@/components/settings/SettingsPickerModal";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
  SettingsSwitchRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useTodos } from "@/contexts/TodosContext";
import {
  DEFAULT_REMINDER_LEAD_MINUTES,
  getReminderLeadMinutes,
  REMINDER_LEAD_OPTIONS,
  setReminderLeadMinutes,
  syncReminderLeadFromServer,
} from "@/lib/reminderPrefs";
import { normalizeReminderLeadMinutes } from "@/lib/reminderTiming";
import { syncTodoReminders } from "@/lib/todoReminders";
import { useTheme } from "@/lib/theme";

export default function NotificationsSettingsScreen() {
  const { token, user, updateUser } = useAuth();
  const { todos } = useTodos();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const [reminderLeadPickerOpen, setReminderLeadPickerOpen] = useState(false);
  const [reminderLeadMinutes, setReminderLeadMinutesState] = useState(
    DEFAULT_REMINDER_LEAD_MINUTES,
  );

  useEffect(() => {
    if (user?.reminder_lead_minutes != null) {
      const minutes = normalizeReminderLeadMinutes(user.reminder_lead_minutes);
      setReminderLeadMinutesState(minutes);
      void syncReminderLeadFromServer(minutes);
      return;
    }
    void getReminderLeadMinutes().then(setReminderLeadMinutesState);
  }, [user?.reminder_lead_minutes]);

  const saveReminderLead = useCallback(
    async (minutes: number) => {
      const normalized = normalizeReminderLeadMinutes(minutes);
      setReminderLeadMinutesState(normalized);
      await setReminderLeadMinutes(normalized);
      try {
        await updateUser({ reminder_lead_minutes: normalized });
      } catch {
        Alert.alert(t("todos.error"), t("common.error"));
      }
      await syncTodoReminders(todos);
    },
    [t, todos, updateUser],
  );

  if (!token) return <Redirect href="/login" />;

  return (
    <>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + 24 }]}
      >
        <SettingsGroup styles={s}>
          <SettingsSwitchRow
            title={t("settings.push_notifications")}
            value={user?.push_notifications_enabled ?? true}
            onValueChange={(v) => {
              void updateUser({ push_notifications_enabled: v }).catch(() => {});
            }}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.reminder_lead")}
            value={t("settings.reminder_lead_value", { count: reminderLeadMinutes })}
            onPress={() => setReminderLeadPickerOpen(true)}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>
      </ScrollView>

      <SettingsPickerModal
        visible={reminderLeadPickerOpen}
        title={t("settings.reminder_lead")}
        selectedKey={String(reminderLeadMinutes)}
        options={REMINDER_LEAD_OPTIONS.map((minutes) => ({
          key: String(minutes),
          label: t("settings.reminder_lead_value", { count: minutes }),
        }))}
        onClose={() => setReminderLeadPickerOpen(false)}
        onSelect={(key) => void saveReminderLead(Number(key))}
        styles={s}
        theme={theme}
      />
    </>
  );
}
