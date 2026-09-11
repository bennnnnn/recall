import { useCallback, useMemo, useState } from "react";
import { Alert, ScrollView, View } from "react-native";
import { Redirect, useFocusEffect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { StateView } from "@/components/StateView";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { api, type Chat } from "@/lib/api";
import { invalidateChatListCache } from "@/lib/cache/chatListCache";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

export default function ArchivedChatsScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const feedback = useActionFeedbackOptional();
  const [chats, setChats] = useState<Chat[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const list = await api.listChats(token);
      setChats(list.archived ?? []);
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

  const unarchive = async (chat: Chat) => {
    if (!token || busyId) return;
    setBusyId(chat.id);
    try {
      await api.setArchive(token, chat.id, false);
      invalidateChatListCache();
      setChats((rows) => rows.filter((row) => row.id !== chat.id));
    } catch {
      reportRecoverableError(feedback, t("chat.archive_failed"));
    } finally {
      setBusyId(null);
    }
  };

  const confirmDelete = (chat: Chat) => {
    if (!token || busyId) return;
    Alert.alert(t("chat.delete_confirm_title"), t("chat.delete_confirm_body"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("common.delete"),
        style: "destructive",
        onPress: () => {
          void (async () => {
            if (!token) return;
            setBusyId(chat.id);
            try {
              await api.deleteChat(token, chat.id);
              invalidateChatListCache();
              setChats((rows) => rows.filter((row) => row.id !== chat.id));
            } catch {
              reportRecoverableError(feedback, t("chat.delete_failed"));
            } finally {
              setBusyId(null);
            }
          })();
        },
      },
    ]);
  };

  if (!token) return <Redirect href="/login" />;

  if (loading && chats.length === 0) {
    return <StateView variant="loading" title={t("settings.archived_chats")} />;
  }

  if (!loading && chats.length === 0) {
    return (
      <StateView
        variant="empty"
        icon="archive-outline"
        title={t("settings.archived_chats_empty")}
      />
    );
  }

  return (
    <ScrollView
      style={s.scroll}
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
    >
      {chats.map((chat) => (
        <SettingsGroup key={chat.id} styles={s}>
          <SettingsLinkRow
            title={chat.title?.trim() || t("common.untitled")}
            onPress={() => void unarchive(chat)}
            value={t("chat.unarchive")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("chat.delete")}
            danger
            onPress={() => confirmDelete(chat)}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>
      ))}
    </ScrollView>
  );
}
