import { useCallback, useEffect, useMemo, useState } from "react";
import { ScrollView, View } from "react-native";
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
} from "@/lib/memoryListCache";
import { useTheme } from "@/lib/theme";

export default function MemorySettingsScreen() {
  const { token, user, updateUser } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [memCount, setMemCount] = useState(0);

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
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + 24 }]}
    >
      <SettingsGroup styles={s}>
        <SettingsSwitchRow
          title={t("settings.memory")}
          value={user?.memory_enabled ?? true}
          onValueChange={(v) => {
            void updateUser({ memory_enabled: v }).catch(() => {});
          }}
          styles={s}
          theme={theme}
        />
        <View style={s.menuSeparator} />
        <SettingsLinkRow
          title={t("settings.memory_view")}
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
