import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, ScrollView, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
  SettingsSwitchRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import {
  fetchMemories,
  prefetchMemories,
} from "@/lib/cache/memoryListCache";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

export default function MemorySettingsScreen() {
  const { token, user, updateUser } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [memCount, setMemCount] = useState(0);
  const [saving, setSaving] = useState(false);

  const loadMemories = useCallback(async () => {
    if (!token) return;
    const memories = await fetchMemories(token);
    if (memories) setMemCount(memories.length);
  }, [token]);

  useEffect(() => {
    void loadMemories();
  }, [loadMemories]);

  if (!token) return <Redirect href="/login" />;

  return (
    <ScrollView
      style={s.scroll}
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
    >
      <SettingsGroup styles={s}>
        <SettingsSwitchRow
          icon="cube-outline"
          title={t("settings.memory")}
          subtitle={t("settings.memory_desc")}
          value={user?.memory_enabled ?? true}
          disabled={saving}
          onValueChange={(v) => {
            setSaving(true);
            void updateUser({ memory_enabled: v })
              .catch(() => {
                Alert.alert(t("common.error"), t("common.error"));
              })
              .finally(() => setSaving(false));
          }}
          styles={s}
          theme={theme}
        />
        <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
        <SettingsLinkRow
          icon="book-outline"
          title={t("settings.memory_view")}
          subtitle={t("settings.memory_empty")}
          value={
            memCount > 0
              ? t("settings.memory_count", { count: memCount })
              : undefined
          }
          onPress={() => {
            if (token) prefetchMemories(token);
            router.push("/memory");
          }}
          styles={s}
          theme={theme}
        />
      </SettingsGroup>
    </ScrollView>
  );
}
