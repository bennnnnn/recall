import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { StateView } from "@/ui/feedback/StateView";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useMemoryToggle } from "@/features/memory/hooks/useMemoryToggle";
import { invalidateMemoryDocuments } from "@/features/memory/model/memoryDocumentsCache";
import { api } from "@/lib/api";
import {
  fetchMemories,
  getCachedMemories,
  prefetchMemories,
  setMemoriesCache,
  subscribeMemoriesCache,
} from "@/features/memory/model/memoryListCache";
import { notifyDestructive } from "@/lib/haptics";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { confirmDialog } from "@/ui/overlay/dialogs";

export default function MemorySettingsScreen() {
  const view = useAccountViewOwner();
  return <MemorySettingsContent key={view.key} isCurrentView={view.isCurrent} />;
}

function MemorySettingsContent({ isCurrentView }: { isCurrentView: () => boolean }) {
  const { token, user, updateUser } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [memCount, setMemCount] = useState(0);
  const [loadError, setLoadError] = useState(false);
  const [busy, setBusy] = useState(false);
  const requestRef = useRef(0);
  const feedback = useActionFeedbackOptional();
  const { saving, toggle } = useMemoryToggle(isCurrentView, useCallback(() => {
    reportRecoverableError(feedback, t("common.error"));
  }, [feedback, t]));

  const onError = useCallback(() => {
    reportRecoverableError(feedback, t("common.error"));
  }, [feedback, t]);

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

  const toggleSensitive = useCallback((enabled: boolean) => {
    if (!isCurrentView() || busy || saving) return;
    void updateUser({ memory_include_sensitive: enabled }).catch(onError);
  }, [isCurrentView, busy, saving, updateUser, onError]);

  const confirmClearAll = useCallback(() => {
    if (!token || !isCurrentView() || busy) return;
    void confirmDialog({
      title: t("settings.memory_clear_all_confirm_title"),
      message: t("settings.memory_clear_all_confirm_body"),
      cancelLabel: t("common.cancel"),
      confirmLabel: t("common.delete"),
      destructive: true,
    }).then((ok) => {
      if (!ok) return;
      void (async () => {
        if (!isCurrentView()) return;
        setBusy(true);
        try {
          await api.clearMemories(token);
          invalidateMemoryDocuments();
          if (!isCurrentView()) return;
          notifyDestructive();
          setMemoriesCache([]);
          setMemCount(0);
        } catch {
          if (isCurrentView()) onError();
        } finally {
          if (isCurrentView()) setBusy(false);
        }
      })();
    });
  }, [token, isCurrentView, busy, t, onError]);

  if (!token) return <Redirect href="/login" />;

  return (
    <ScrollView
      style={s.scroll}
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
    >
      <SettingsGroup styles={s}>
        <SettingsSwitchRow
          icon="box"
          title={t("settings.memory")}
          subtitle={t("settings.memory_desc")}
          value={user?.memory_enabled ?? true}
          disabled={saving || busy}
          busy={saving}
          onValueChange={toggle}
          styles={s}
          theme={theme}
        />
        <View style={s.menuSeparator} />
        <SettingsSwitchRow
          icon="shield"
          title={t("settings.memory_include_sensitive")}
          subtitle={t("settings.memory_include_sensitive_desc")}
          value={user?.memory_include_sensitive ?? false}
          disabled={saving || busy}
          onValueChange={toggleSensitive}
          styles={s}
          theme={theme}
        />
        <View style={s.menuSeparator} />
        <SettingsLinkRow
          icon="book"
          title={t("settings.memory_view")}
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
      <SettingsGroup styles={s}>
        <SettingsLinkRow
          icon="trash"
          title={t("settings.memory_clear_all")}
          danger
          onPress={confirmClearAll}
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
