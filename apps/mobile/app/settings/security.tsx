import { useCallback, useMemo, useState } from "react";
import { View } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { StateView } from "@/ui/feedback/StateView";
import { SettingsSkeleton } from "@/components/settings/SettingsSkeleton";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
  SettingsValueRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { api, type AuthSession } from "@/lib/api";
import { notifyDestructive } from "@/lib/haptics";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";
import { confirmDialog } from "@/ui/overlay/dialogs";

function formatSeen(iso: string | null, t: (key: string) => string): string {
  if (!iso) return t("settings.unknown_device");
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return t("settings.unknown_device");
  return date.toLocaleString();
}

export default function SecuritySettingsScreen() {
  const { token, signOut } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const feedback = useActionFeedbackOptional();
  const [sessions, setSessions] = useState<AuthSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setLoadError(false);
    try {
      const data = await api.listSessions(token);
      setSessions(data.sessions ?? []);
    } catch {
      // A failed load must not look like "no other sessions".
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const revoke = (session: AuthSession) => {
    if (!token || session.current || busyId) return;
    void confirmDialog({
      title: t("settings.revoke_session"),
      message: t("settings.revoke_session_confirm"),
      cancelLabel: t("common.cancel"),
      confirmLabel: t("settings.revoke_session"),
      destructive: true,
    }).then((ok) => {
      if (!ok) return;
      void (async () => {
        if (!token) return;
        setBusyId(session.id);
        try {
          await api.revokeSession(token, session.id);
          notifyDestructive();
          setSessions((rows) => rows.filter((row) => row.id !== session.id));
        } catch {
          reportRecoverableError(feedback, t("common.error"));
        } finally {
          setBusyId(null);
        }
      })();
    });
  };

  const confirmLogoutAll = () => {
    if (!token || busyId) return;
    void confirmDialog({
      title: t("settings.sign_out_all"),
      message: t("settings.sign_out_all_confirm"),
      cancelLabel: t("common.cancel"),
      confirmLabel: t("settings.sign_out_all"),
      destructive: true,
    }).then((ok) => {
      if (!ok) return;
      void (async () => {
        if (!token) return;
        setBusyId("all");
        try {
          await api.logoutAll(token);
          await signOut();
          notifyDestructive();
          router.replace("/login");
        } catch {
          reportRecoverableError(feedback, t("common.error"));
          setBusyId(null);
        }
      })();
    });
  };

  if (!token) return <Redirect href="/login" />;

  return (
    <FlashList
      data={sessions}
      keyExtractor={(session) => session.id}
      style={s.scroll}
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
      ListEmptyComponent={
        loading && !loadError ? (
          <SettingsSkeleton
            rows={3}
            contained
            accessibilityLabel={t("settings.security")}
          />
        ) : loadError ? (
          <StateView
            variant="error"
            title={t("common.error")}
            onRetry={() => void load()}
          />
        ) : null
      }
      renderItem={({ item: session }) => (
        <SettingsGroup styles={s}>
          <SettingsValueRow
            title={session.device_label?.trim() || t("settings.unknown_device")}
            subtitle={formatSeen(session.last_seen_at, t)}
            value={session.current ? t("settings.this_device") : undefined}
            styles={s}
            theme={theme}
          />
          {session.current ? null : (
            <>
              <View style={s.menuSeparator} />
              <SettingsLinkRow
                title={t("settings.revoke_session")}
                danger
                onPress={() => revoke(session)}
                styles={s}
                theme={theme}
              />
            </>
          )}
        </SettingsGroup>
      )}
      ListFooterComponent={
        <SettingsGroup styles={s}>
          <SettingsLinkRow
            title={t("settings.sign_out_all")}
            danger
            onPress={confirmLogoutAll}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>
      }
    />
  );
}
