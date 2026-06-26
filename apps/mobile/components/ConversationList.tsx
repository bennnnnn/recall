import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { closeDrawer, startNewChatGlobal } from "@/lib/drawer";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Avatar } from "@/components/Avatar";
import { C } from "@/constants/Colors";
import { useAuth } from "@/contexts/AuthContext";
import { useDrawer } from "@/contexts/DrawerContext";
import { api, Chat } from "@/lib/api";
import { tap } from "@/lib/haptics";
import { shareConversation } from "@/lib/share";

const TOP_CHROME = 92;
const SEARCH_EXTRA = 44;
const FOOTER_CHROME = 54;
const FADE_EXTRA = 40;

const DRAWER_ANIM_MS = 280;

function deferUntilIdle(fn: () => void): () => void {
  if (typeof requestIdleCallback === "function") {
    const id = requestIdleCallback(fn);
    return () => cancelIdleCallback(id);
  }
  const id = setTimeout(fn, DRAWER_ANIM_MS);
  return () => clearTimeout(id);
}

function ChatRow({
  chat,
  onOpen,
  onLongPress,
}: {
  chat: Chat;
  onOpen: () => void;
  onLongPress: () => void;
}) {
  return (
    <Pressable style={r.row} onPress={onOpen} onLongPress={onLongPress}>
      <Ionicons
        name={chat.pinned ? "bookmark" : "chatbubble-outline"}
        size={16}
        color={chat.pinned ? C.primary : C.textTertiary}
        style={r.rowIcon}
      />
      <Text style={r.title} numberOfLines={1}>
        {chat.title ?? "New chat"}
      </Text>
    </Pressable>
  );
}

function Section({
  title,
  chats,
  onOpen,
  onLongPress,
}: {
  title: string;
  chats: Chat[];
  onOpen: (id: string) => void;
  onLongPress: (chat: Chat) => void;
}) {
  if (!chats.length) return null;
  return (
    <View style={s.section}>
      <Text style={s.sectionTitle}>{title}</Text>
      {chats.map((c) => (
        <ChatRow
          key={c.id}
          chat={c}
          onOpen={() => onOpen(c.id)}
          onLongPress={() => onLongPress(c)}
        />
      ))}
    </View>
  );
}

export function ConversationList(_props: unknown) {
  const { token, user } = useAuth();
  const { isOpen } = useDrawer();
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [groups, setGroups] = useState<{
    pinned: Chat[];
    today: Chat[];
    yesterday: Chat[];
    earlier: Chat[];
  }>({ pinned: [], today: [], yesterday: [], earlier: [] });
  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [error, setError] = useState(false);

  const allChats = useMemo(
    () => [
      ...groups.pinned,
      ...groups.today,
      ...groups.yesterday,
      ...groups.earlier,
    ],
    [groups],
  );

  const filtered = useMemo(() => {
    if (!query.trim()) return groups;
    const q = query.toLowerCase();
    const keep = (c: Chat) => (c.title ?? "New chat").toLowerCase().includes(q);
    return {
      pinned: groups.pinned.filter(keep),
      today: groups.today.filter(keep),
      yesterday: groups.yesterday.filter(keep),
      earlier: groups.earlier.filter(keep),
    };
  }, [groups, query]);

  const load = useCallback(
    async (background = false) => {
      if (!token) {
        setLoading(false);
        return;
      }
      if (background) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(false);
      try {
        setGroups(await api.listChats(token));
      } catch {
        if (!background) setError(true);
      } finally {
        if (background) {
          setRefreshing(false);
        } else {
          setLoading(false);
        }
      }
    },
    [token],
  );

  // Prefetch history on login so the drawer can open instantly.
  useEffect(() => {
    load(false);
  }, [load]);

  // Refresh after the slide animation — keep cached rows visible immediately.
  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    const cancel = deferUntilIdle(() => {
      if (!cancelled) void load(true);
    });
    return () => {
      cancelled = true;
      cancel();
    };
  }, [isOpen, load]);

  const openChat = (id: string) => {
    closeDrawer();
    router.setParams({ chatId: id });
  };

  const newChat = () => {
    closeDrawer();
    startNewChatGlobal();
  };

  const showRowMenu = (chat: Chat) => {
    tap();
    Alert.alert(chat.title ?? "New chat", undefined, [
      {
        text: chat.pinned ? "Unpin" : "Pin",
        onPress: async () => {
          if (!token) return;
          try {
            await api.setPin(token, chat.id, !chat.pinned);
            load();
          } catch {
            /* ignore */
          }
        },
      },
      {
        text: "Share",
        onPress: async () => {
          if (!token) return;
          try {
            const msgs = await api.listAllMessages(token, chat.id);
            await shareConversation(chat.title, msgs);
          } catch {
            /* ignore */
          }
        },
      },
      {
        text: "Delete",
        style: "destructive",
        onPress: () => {
          Alert.alert(
            "Delete chat",
            "This conversation will be permanently removed.",
            [
              { text: "Cancel", style: "cancel" },
              {
                text: "Delete",
                style: "destructive",
                onPress: async () => {
                  if (!token) return;
                  try {
                    await api.deleteChat(token, chat.id);
                    load();
                  } catch {
                    /* ignore */
                  }
                },
              },
            ],
          );
        },
      },
      { text: "Cancel", style: "cancel" },
    ]);
  };

  const topInset =
    insets.top + 8 + TOP_CHROME + (searchOpen ? SEARCH_EXTRA : 0);
  const bottomInset = insets.bottom + 8 + FOOTER_CHROME;
  const topFadeHeight = topInset + FADE_EXTRA;
  const bottomFadeHeight = bottomInset + FADE_EXTRA;

  const listBody =
    loading && allChats.length === 0 ? (
      <View style={s.center}>
        <ActivityIndicator color={C.primary} />
      </View>
    ) : error && allChats.length === 0 ? (
      <View style={s.center}>
        <Ionicons
          name="cloud-offline-outline"
          size={36}
          color={C.textTertiary}
        />
        <Text style={s.emptyText}>Can't reach server</Text>
        <Pressable style={s.retryBtn} onPress={() => void load()}>
          <Text style={s.retryText}>Retry</Text>
        </Pressable>
      </View>
    ) : allChats.length === 0 ? (
      <View style={s.center}>
        <Text style={s.emptyText}>No conversations yet</Text>
      </View>
    ) : (
      <ScrollView
        style={s.list}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{
          paddingTop: topInset,
          paddingBottom: bottomInset,
        }}
      >
        <Section
          title="Pinned"
          chats={filtered.pinned}
          onOpen={openChat}
          onLongPress={showRowMenu}
        />
        <Section
          title="Today"
          chats={filtered.today}
          onOpen={openChat}
          onLongPress={showRowMenu}
        />
        <Section
          title="Yesterday"
          chats={filtered.yesterday}
          onOpen={openChat}
          onLongPress={showRowMenu}
        />
        <Section
          title="Earlier"
          chats={filtered.earlier}
          onOpen={openChat}
          onLongPress={showRowMenu}
        />
      </ScrollView>
    );

  return (
    <View style={s.root}>
      {listBody}

      {/* Top fade — topics dim as they scroll under the header */}
      <LinearGradient
        pointerEvents="none"
        colors={[
          C.bg,
          "rgba(255,255,255,0.98)",
          "rgba(255,255,255,0.82)",
          "rgba(255,255,255,0.45)",
          "rgba(255,255,255,0)",
        ]}
        locations={[0, 0.25, 0.5, 0.78, 1]}
        style={[s.topFade, { height: topFadeHeight }]}
      />

      {/* Bottom fade — topics dim as they scroll under the footer */}
      <LinearGradient
        pointerEvents="none"
        colors={[
          "rgba(255,255,255,0)",
          "rgba(255,255,255,0.45)",
          "rgba(255,255,255,0.82)",
          "rgba(255,255,255,0.95)",
        ]}
        locations={[0, 0.35, 0.72, 1]}
        style={[s.bottomFade, { height: bottomFadeHeight }]}
      />

      {/* Floating header — Recall, search, new chat */}
      <View
        style={[s.topOverlay, { paddingTop: insets.top + 8 }]}
        pointerEvents="box-none"
      >
        <View style={s.header}>
          <View style={s.logo}>
            <View style={s.logoIcon}>
              <Text style={s.logoStar}>✦</Text>
            </View>
            <Text style={s.logoText}>Recall</Text>
            <Pressable
              hitSlop={8}
              style={s.searchBtn}
              onPress={() => {
                setSearchOpen((v) => {
                  if (v) setQuery("");
                  return !v;
                });
              }}
            >
              {refreshing ? (
                <ActivityIndicator size="small" color={C.textSecondary} />
              ) : (
                <Ionicons
                  name={searchOpen ? "close-outline" : "search-outline"}
                  size={20}
                  color={C.textSecondary}
                />
              )}
            </Pressable>
          </View>
        </View>

        {searchOpen && (
          <View style={s.searchRow}>
            <TextInput
              style={s.searchInput}
              placeholder="Search chats..."
              placeholderTextColor={C.textTertiary}
              value={query}
              onChangeText={setQuery}
              autoFocus
            />
          </View>
        )}

        <Pressable style={s.newBtn} onPress={newChat}>
          <Ionicons name="create-outline" size={18} color={C.text} />
          <Text style={s.newBtnText}>New chat</Text>
        </Pressable>
      </View>

      {/* Floating footer — user + settings */}
      <View
        style={[s.footer, { paddingBottom: insets.bottom + 8 }]}
        pointerEvents="box-none"
      >
        <Avatar name={user?.name ?? null} uri={user?.avatar_url} size={34} />
        <Text style={s.footerName} numberOfLines={1}>
          {user?.name ?? "You"}
        </Text>
        <Pressable
          style={s.settingsBtn}
          onPress={() => {
            closeDrawer();
            router.push("/settings");
          }}
        >
          <Ionicons name="settings-outline" size={22} color={C.textSecondary} />
        </Pressable>
      </View>
    </View>
  );
}

const r = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 9,
    paddingHorizontal: 14,
    gap: 10,
  },
  rowIcon: { flexShrink: 0 },
  title: { flex: 1, fontSize: 14, fontWeight: "500", color: C.text },
});

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg, overflow: "visible" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: 8 },
  topFade: { position: "absolute", top: 0, left: 0, right: 0, zIndex: 50 },
  bottomFade: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    zIndex: 50,
  },
  topOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    zIndex: 100,
    backgroundColor: "transparent",
  },
  header: { paddingHorizontal: 16, paddingBottom: 10 },
  logo: { flexDirection: "row", alignItems: "center", gap: 8 },
  logoIcon: {
    width: 28,
    height: 28,
    borderRadius: 8,
    backgroundColor: C.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  logoStar: { fontSize: 13, color: "#fff" },
  logoText: {
    fontSize: 20,
    fontWeight: "800",
    color: C.text,
    letterSpacing: -0.5,
  },
  searchBtn: { marginLeft: 2, padding: 4 },
  searchRow: {
    marginHorizontal: 16,
    marginBottom: 8,
    backgroundColor: C.surface,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  searchInput: { fontSize: 15, color: C.text },
  newBtn: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: 14,
    marginBottom: 4,
    paddingHorizontal: 14,
    paddingVertical: 10,
    gap: 10,
  },
  newBtnText: { fontSize: 15, fontWeight: "600", color: C.text },
  list: { flex: 1 },
  section: { marginTop: 14 },
  sectionTitle: {
    fontSize: 11,
    fontWeight: "700",
    color: C.textTertiary,
    textTransform: "uppercase",
    letterSpacing: 0.8,
    paddingHorizontal: 14,
    marginBottom: 2,
  },
  emptyText: { fontSize: 15, color: C.textSecondary, fontWeight: "500" },
  retryBtn: {
    paddingHorizontal: 20,
    paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: C.primary,
  },
  retryText: { fontSize: 14, fontWeight: "600", color: "#fff" },
  footer: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    zIndex: 100,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 14,
    paddingTop: 12,
    backgroundColor: "transparent",
    gap: 10,
  },
  avatar: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: C.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: { fontSize: 13, fontWeight: "700", color: "#fff" },
  footerName: { flex: 1, fontSize: 14, fontWeight: "600", color: C.text },
  settingsBtn: {
    padding: 6,
    borderRadius: 10,
    backgroundColor: C.bg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
  },
});
