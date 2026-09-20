import { useCallback, useMemo, useState } from "react";
import { Alert, View } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { Redirect, useFocusEffect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { StateView } from "@/components/StateView";
import { SettingsSkeleton } from "@/components/settings/SettingsSkeleton";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { api, type Chat } from "@/lib/api";
import { invalidateChatListCache } from "@/lib/cache/chatListCache";
import { notifyDestructive } from "@/lib/haptics";
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
  const [loadError, setLoadError] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setLoadError(false);
    try {
      const list = await api.listChats(token);
      setChats(list.archived ?? []);
    } catch {
      // A failed load must not masquerade as an empty list.
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
              notifyDestructive();
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

  if (loading && chats.length === 0 && !loadError) {
    return (
      <SettingsSkeleton
        accessibilityLabel={t("settings.archived_chats")}
      />
    );
  }

  if (loadError && chats.length === 0) {
    return (
      <StateView
        variant="error"
        title={t("common.error")}
        onRetry={() => void load()}
      />
    );
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
    <FlashList
      data={chats}
      keyExtractor={(chat) => chat.id}
      style={s.scroll}
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
      renderItem={({ item: chat }) => (
        <SettingsGroup styles={s}>
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
      )}
    />
  );
}
