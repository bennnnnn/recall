import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { StateView } from "@/components/StateView";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useMemoryToggle } from "@/hooks/useMemoryToggle";
import {
  fetchMemories,
  getCachedMemories,
  prefetchMemories,
  subscribeMemoriesCache,
} from "@/lib/cache/memoryListCache";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

export default function MemorySettingsScreen() {
  const view = useAccountViewOwner();
  return <MemorySettingsContent key={view.key} isCurrentView={view.isCurrent} />;
}

function MemorySettingsContent({ isCurrentView }: { isCurrentView: () => boolean }) {
  const { token, user } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [memCount, setMemCount] = useState(0);
  const [loadError, setLoadError] = useState(false);
  const requestRef = useRef(0);
  const feedback = useActionFeedbackOptional();
  const { saving, toggle } = useMemoryToggle(isCurrentView, useCallback(() => {
    if (feedback) feedback.error(t("common.error"));
    else Alert.alert(t("common.error"), t("common.error"));
  }, [feedback, t]));

  const loadMemories = useCallback(async (force = false) => {
    if (!token || !isCurrentView()) return;
    const request = ++requestRef.current;
    setLoadError(false);
    const memories = await fetchMemories(token, { force });
    if (!isCurrentView() || request !== requestRef.current) return;
    if (memories) setMemCount((getCachedMemories() ?? memories).length);
    else setLoadError(true);
  }, [token, isCurrentView]);

  useEffect(() => subscribeMemoriesCache(() => {
    if (isCurrentView()) setMemCount(getCachedMemories()?.length ?? 0);
  }), [isCurrentView]);

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
          busy={saving}
          onValueChange={toggle}
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
            if (!isCurrentView()) return;
            if (token) prefetchMemories(token);
            router.push("/memory");
          }}
          styles={s}
          theme={theme}
        />
      </SettingsGroup>
      {loadError ? <StateView
        variant="error"
        title={t("common.error")}
        onRetry={() => void loadMemories(true)}
        retryLabel={t("common.retry")}
      /> : null}
    </ScrollView>
  );
}
