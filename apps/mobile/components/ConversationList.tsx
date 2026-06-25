import { useCallback, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { closeDrawer } from '@/lib/drawer';
import { useFocusEffect, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { C } from '@/constants/Colors';
import { useAuth } from '@/contexts/AuthContext';
import { api, Chat } from '@/lib/api';

const TOP_CHROME = 92;
const SEARCH_EXTRA = 44;
const FOOTER_CHROME = 54;
const FADE_EXTRA = 40;

function ChatRow({ chat, onOpen }: { chat: Chat; onOpen: () => void }) {
  return (
    <Pressable style={r.row} onPress={onOpen}>
      <Ionicons name="chatbubble-outline" size={16} color={C.textTertiary} style={r.rowIcon} />
      <Text style={r.title} numberOfLines={1}>{chat.title ?? 'New chat'}</Text>
    </Pressable>
  );
}

function Section({ title, chats, onOpen }: {
  title: string; chats: Chat[];
  onOpen: (id: string) => void;
}) {
  if (!chats.length) return null;
  return (
    <View style={s.section}>
      <Text style={s.sectionTitle}>{title}</Text>
      {chats.map((c) => (
        <ChatRow key={c.id} chat={c} onOpen={() => onOpen(c.id)} />
      ))}
    </View>
  );
}

export function ConversationList(_props: unknown) {
  const { token, user } = useAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const [loading, setLoading] = useState(true);
  const [groups, setGroups] = useState<{ today: Chat[]; yesterday: Chat[]; earlier: Chat[] }>({
    today: [], yesterday: [], earlier: [],
  });
  const [query, setQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [error, setError] = useState(false);

  const allChats = useMemo(
    () => [...groups.today, ...groups.yesterday, ...groups.earlier],
    [groups],
  );

  const filtered = useMemo(() => {
    if (!query.trim()) return groups;
    const q = query.toLowerCase();
    const keep = (c: Chat) => (c.title ?? 'New chat').toLowerCase().includes(q);
    return {
      today: groups.today.filter(keep),
      yesterday: groups.yesterday.filter(keep),
      earlier: groups.earlier.filter(keep),
    };
  }, [groups, query]);

  const load = useCallback(async () => {
    if (!token) { setLoading(false); return; }
    setLoading(true);
    setError(false);
    try {
      setGroups(await api.listChats(token));
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const openChat = (id: string) => {
    closeDrawer();
    router.setParams({ chatId: id });
  };

  const newChat = () => {
    closeDrawer();
    router.setParams({ chatId: undefined });
  };

  const initials = user?.name
    ? user.name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()
    : '?';

  const topInset = insets.top + 8 + TOP_CHROME + (searchOpen ? SEARCH_EXTRA : 0);
  const bottomInset = insets.bottom + 8 + FOOTER_CHROME;
  const topFadeHeight = topInset + FADE_EXTRA;
  const bottomFadeHeight = bottomInset + FADE_EXTRA;

  const listBody = loading ? (
    <View style={s.center}><ActivityIndicator color={C.primary} /></View>
  ) : error ? (
    <View style={s.center}>
      <Ionicons name="cloud-offline-outline" size={36} color={C.textTertiary} />
      <Text style={s.emptyText}>Can't reach server</Text>
      <Pressable style={s.retryBtn} onPress={load}>
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
      contentContainerStyle={{ paddingTop: topInset, paddingBottom: bottomInset }}>
      <Section title="Today" chats={filtered.today} onOpen={openChat} />
      <Section title="Yesterday" chats={filtered.yesterday} onOpen={openChat} />
      <Section title="Earlier" chats={filtered.earlier} onOpen={openChat} />
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
          'rgba(255,255,255,0.98)',
          'rgba(255,255,255,0.82)',
          'rgba(255,255,255,0.45)',
          'rgba(255,255,255,0)',
        ]}
        locations={[0, 0.25, 0.5, 0.78, 1]}
        style={[s.topFade, { height: topFadeHeight }]}
      />

      {/* Bottom fade — topics dim as they scroll under the footer */}
      <LinearGradient
        pointerEvents="none"
        colors={[
          'rgba(255,255,255,0)',
          'rgba(255,255,255,0.45)',
          'rgba(255,255,255,0.82)',
          'rgba(255,255,255,0.95)',
        ]}
        locations={[0, 0.35, 0.72, 1]}
        style={[s.bottomFade, { height: bottomFadeHeight }]}
      />

      {/* Floating header — Recall, search, new chat */}
      <View style={[s.topOverlay, { paddingTop: insets.top + 8 }]} pointerEvents="box-none">
        <View style={s.header}>
          <View style={s.logo}>
            <View style={s.logoIcon}><Text style={s.logoStar}>✦</Text></View>
            <Text style={s.logoText}>Recall</Text>
            <Pressable
              hitSlop={8}
              style={s.searchBtn}
              onPress={() => {
                setSearchOpen((v) => {
                  if (v) setQuery('');
                  return !v;
                });
              }}>
              <Ionicons
                name={searchOpen ? 'close-outline' : 'search-outline'}
                size={20}
                color={C.textSecondary}
              />
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
      <View style={[s.footer, { paddingBottom: insets.bottom + 8 }]} pointerEvents="box-none">
        <View style={s.avatar}><Text style={s.avatarText}>{initials}</Text></View>
        <Text style={s.footerName} numberOfLines={1}>{user?.name ?? 'You'}</Text>
        <Pressable style={s.settingsBtn} onPress={() => { closeDrawer(); router.push('/settings'); }}>
          <Ionicons name="settings-outline" size={22} color={C.textSecondary} />
        </Pressable>
      </View>
    </View>
  );
}

const r = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', paddingVertical: 9, paddingHorizontal: 14, gap: 10 },
  rowIcon: { flexShrink: 0 },
  title: { flex: 1, fontSize: 14, fontWeight: '500', color: C.text },
});

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg, overflow: 'visible' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 8 },
  topFade: { position: 'absolute', top: 0, left: 0, right: 0, zIndex: 50 },
  bottomFade: { position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 50 },
  topOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 100,
    backgroundColor: 'transparent',
  },
  header: { paddingHorizontal: 16, paddingBottom: 10 },
  logo: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  logoIcon: { width: 28, height: 28, borderRadius: 8, backgroundColor: C.primary, alignItems: 'center', justifyContent: 'center' },
  logoStar: { fontSize: 13, color: '#fff' },
  logoText: { fontSize: 20, fontWeight: '800', color: C.text, letterSpacing: -0.5 },
  searchBtn: { marginLeft: 2, padding: 4 },
  searchRow: { marginHorizontal: 16, marginBottom: 8, backgroundColor: C.surface, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10 },
  searchInput: { fontSize: 15, color: C.text },
  newBtn: { flexDirection: 'row', alignItems: 'center', marginHorizontal: 14, marginBottom: 4, paddingHorizontal: 14, paddingVertical: 10, gap: 10 },
  newBtnText: { fontSize: 15, fontWeight: '600', color: C.text },
  list: { flex: 1 },
  section: { marginTop: 14 },
  sectionTitle: { fontSize: 11, fontWeight: '700', color: C.textTertiary, textTransform: 'uppercase', letterSpacing: 0.8, paddingHorizontal: 14, marginBottom: 2 },
  emptyText: { fontSize: 15, color: C.textSecondary, fontWeight: '500' },
  retryBtn: { paddingHorizontal: 20, paddingVertical: 8, borderRadius: 10, backgroundColor: C.primary },
  retryText: { fontSize: 14, fontWeight: '600', color: '#fff' },
  footer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    zIndex: 100,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingTop: 12,
    backgroundColor: 'transparent',
    gap: 10,
  },
  avatar: { width: 34, height: 34, borderRadius: 17, backgroundColor: C.primary, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  footerName: { flex: 1, fontSize: 14, fontWeight: '600', color: C.text },
  settingsBtn: {
    padding: 6,
    borderRadius: 10,
    backgroundColor: C.bg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
  },
});
