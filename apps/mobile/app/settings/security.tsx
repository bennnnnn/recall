import { useCallback, useMemo, useState } from "react";
import { Alert, ScrollView, View } from "react-native";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { StateView } from "@/components/StateView";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
  SettingsValueRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { api, type AuthSession } from "@/lib/api";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

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
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await api.listSessions(token);
      setSessions(data.sessions ?? []);
    } catch {
      reportRecoverableError(feedback, t("common.error"));
    } finally {
      setLoading(false);
    }
  }, [token, feedback, t]);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const revoke = (session: AuthSession) => {
    if (!token || session.current || busyId) return;
    Alert.alert(t("settings.revoke_session"), t("settings.revoke_session_confirm"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("settings.revoke_session"),
        style: "destructive",
        onPress: () => {
          void (async () => {
            if (!token) return;
            setBusyId(session.id);
            try {
              await api.revokeSession(token, session.id);
              setSessions((rows) => rows.filter((row) => row.id !== session.id));
            } catch {
              reportRecoverableError(feedback, t("common.error"));
            } finally {
              setBusyId(null);
            }
          })();
        },
      },
    ]);
  };

  const confirmLogoutAll = () => {
    if (!token || busyId) return;
    Alert.alert(t("settings.sign_out_all"), t("settings.sign_out_all_confirm"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("settings.sign_out_all"),
        style: "destructive",
        onPress: () => {
          void (async () => {
            if (!token) return;
            setBusyId("all");
            try {
              await api.logoutAll(token);
              await signOut();
              router.replace("/login");
            } catch {
              reportRecoverableError(feedback, t("common.error"));
              setBusyId(null);
            }
          })();
        },
      },
    ]);
  };

  if (!token) return <Redirect href="/login" />;

  return (
    <ScrollView
      style={s.scroll}
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
    >
      {loading && sessions.length === 0 ? (
        <StateView variant="loading" title={t("settings.security")} />
      ) : null}
      {sessions.map((session) => (
        <SettingsGroup key={session.id} styles={s}>
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
      ))}
      <SettingsGroup styles={s}>
        <SettingsLinkRow
          title={t("settings.sign_out_all")}
          danger
          onPress={confirmLogoutAll}
          styles={s}
          theme={theme}
        />
      </SettingsGroup>
    </ScrollView>
  );
}
