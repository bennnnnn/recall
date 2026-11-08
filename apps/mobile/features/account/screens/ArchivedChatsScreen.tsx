import { useRef } from "react";
import { StyleSheet } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { Redirect } from "expo-router";
import { useTranslation } from "react-i18next";

import { HeaderButton } from "@/ui/controls/HeaderButton";
import { StateView } from "@/ui/feedback/StateView";
import { ListSeparator } from "@/ui/list/ListGroup";
import { ListRow } from "@/ui/list/ListRow";
import { SettingsSkeleton } from "@/features/account/components/SettingsSkeleton";
import {
  useSettingsAction,
  useSettingsContentStyle,
} from "@/features/account/components/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useFocusedList } from "@/features/account/hooks/useFocusedList";
import { api, type Chat } from "@/lib/api";
import {
  fetchChatList,
  fetchMoreArchivedChats,
  getChatListFetchedAt,
  invalidateChatListCache,
} from "@/features/chat/model/chatListCache";
import { formatDate } from "@/lib/datetime/format";
import { notifyDestructive } from "@/lib/haptics";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

/** The drawer's chat list holds the archived rows too: a fresh one is read from memory,
 * not downloaded again on every visit (code-health audit NET-19). */
async function readArchivedChats(token: string): Promise<Chat[]> {
  const { data, error } = await fetchChatList(token);
  if (error || !data) throw error ?? new Error("chat list unavailable");
  return data.archived ?? [];
}

export default function ArchivedChatsScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const contentStyle = useSettingsContentStyle();
  const action = useSettingsAction();
  const {
    items: chats,
    setItems: setChats,
    loading,
    loadError,
    load,
  } = useFocusedList(token, readArchivedChats, getChatListFetchedAt);

  const drop = (chat: Chat) => setChats((rows) => rows.filter((row) => row.id !== chat.id));

  // Past the first page: the list used to stop at the newest 50 archived chats.
  const paging = useRef(false);
  const loadMore = async () => {
    if (!token || paging.current) return;
    paging.current = true;
    try {
      const grown = await fetchMoreArchivedChats(token);
      if (!grown) return;
      setChats((rows) => {
        const shown = new Set(rows.map((row) => row.id));
        return [...rows, ...grown.archived.filter((chat) => !shown.has(chat.id))];
      });
    } catch {
      // The rows shown stay; reaching the end again tries again.
    } finally {
      paging.current = false;
    }
  };

  const unarchive = (chat: Chat) => {
    if (!token) return;
    void action.run(
      `unarchive:${chat.id}`,
      async () => {
        await api.setArchive(token, chat.id, false);
        invalidateChatListCache();
        drop(chat);
      },
      { errorKey: "chat.archive_failed" },
    );
  };

  const remove = (chat: Chat) => {
    if (!token) return;
    void action.run(
      `delete:${chat.id}`,
      async () => {
        await api.deleteChat(token, chat.id);
        notifyDestructive();
        invalidateChatListCache({ rowsRemoved: true });
        drop(chat);
      },
      {
        errorKey: "chat.delete_failed",
        confirm: {
          title: t("chat.delete_confirm_title"),
          message: t("chat.delete_confirm_body"),
          cancelLabel: t("common.cancel"),
          confirmLabel: t("common.delete"),
          destructive: true,
        },
      },
    );
  };

  if (!token) return <Redirect href="/login" />;

  if (loading && chats.length === 0 && !loadError) {
    return <SettingsSkeleton accessibilityLabel={t("settings.archived_chats")} />;
  }

  if (loadError && chats.length === 0) {
    return <StateView variant="error" title={t("common.error")} onRetry={() => void load()} />;
  }

  if (!loading && chats.length === 0) {
    return <StateView variant="empty" icon="archive" title={t("settings.archived_chats_empty")} />;
  }

  return (
    <FlashList keyboardShouldPersistTaps="handled"
      data={chats}
      keyExtractor={(chat) => chat.id}
      style={{ flex: 1, backgroundColor: theme.bg }}
      contentContainerStyle={[contentStyle, s.list]}
      onEndReached={() => void loadMore()}
      onEndReachedThreshold={0.5}
      ItemSeparatorComponent={ListSeparator}
      renderItem={({ item: chat, index }) => (
        <ArchivedChatRow
          chat={chat}
          edge={{ first: index === 0, last: index === chats.length - 1 }}
          busy={action.busy}
          onUnarchive={unarchive}
          onDelete={remove}
        />
      )}
    />
  );
}

/**
 * One archived chat: its title and last date, and its two actions as buttons on the row,
 * so nothing reads as a subtitle and Delete is plainly this chat's. The rows draw as one
 * rounded group, like the rest of Settings.
 */
function ArchivedChatRow({
  chat,
  edge,
  busy,
  onUnarchive,
  onDelete,
}: {
  chat: Chat;
  edge: { first: boolean; last: boolean };
  busy: string | null;
  onUnarchive: (chat: Chat) => void;
  onDelete: (chat: Chat) => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const title = chat.title?.trim() || t("common.untitled");
  const updated = new Date(chat.updated_at);
  return (
    <ListRow
      title={title}
      subtitle={Number.isNaN(updated.getTime()) ? undefined : formatDate(updated, "monthDayYear")}
      numberOfLines={1}
      style={[edge.first && s.firstRow, edge.last && s.lastRow]}
      trailing={
        <>
          <HeaderButton
            icon="unarchive"
            variant="plain"
            accessibilityLabel={`${t("chat.unarchive")}, ${title}`}
            busy={busy === `unarchive:${chat.id}`}
            disabled={busy !== null}
            onPress={() => onUnarchive(chat)}
          />
          <HeaderButton
            icon="trash"
            variant="plain"
            color={theme.danger}
            accessibilityLabel={`${t("chat.delete")}, ${title}`}
            busy={busy === `delete:${chat.id}`}
            disabled={busy !== null}
            onPress={() => onDelete(chat)}
          />
        </>
      }
    />
  );
}

const s = StyleSheet.create({
  // The gap a Settings group keeps under the header.
  list: { paddingTop: Space.lg },
  firstRow: { borderTopLeftRadius: Radius.xl, borderTopRightRadius: Radius.xl },
  lastRow: { borderBottomLeftRadius: Radius.xl, borderBottomRightRadius: Radius.xl },
});
