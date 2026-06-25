import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Keyboard,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  TouchableWithoutFeedback,
  View,
} from 'react-native';
import { FlashList, FlashListRef } from '@shopify/flash-list';
import { LinearGradient } from 'expo-linear-gradient';
import { openDrawer, registerNewChat } from '@/lib/drawer';
import { Redirect, useLocalSearchParams, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Ionicons } from '@expo/vector-icons';

import { C } from '@/constants/Colors';
import { MessageBubble } from '@/components/MessageBubble';
import { useAuth } from '@/contexts/AuthContext';
import { useDrawer } from '@/contexts/DrawerContext';
import { useChat } from '@/hooks/useChat';
import { api, Message, ModelInfo } from '@/lib/api';
import { tap } from '@/lib/haptics';
import { shareConversation } from '@/lib/share';

const AUTO_OPTION: ModelInfo = {
  id: 'auto',
  label: 'Auto',
  provider: '',
  tier: 'auto',
  description: 'Automatically pick the best model per message',
  available: true,
  input_price_per_m: null,
  output_price_per_m: null,
};

const DEFAULT_MODELS: ModelInfo[] = [
  { id: 'free-chat', label: 'Flash', provider: 'deepseek', tier: 'fast', description: 'Fast, low-cost', available: true, input_price_per_m: null, output_price_per_m: null },
  { id: 'smart-chat', label: 'Pro', provider: 'deepseek', tier: 'smart', description: 'Stronger reasoning', available: true, input_price_per_m: null, output_price_per_m: null },
];

function dotColorForTier(tier: string): string {
  if (tier === 'smart') return '#FF9F0A';
  if (tier === 'max') return '#34C759';
  return '#6C5CE7';
}
const HEADER_BAR_HEIGHT = 52;
const HEADER_FADE_EXTRA = 48;
const COMPOSER_HEIGHT = 108;

export default function ChatScreen() {
  const { token, user } = useAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const drawerOpen = useDrawer().isOpen;
  const { chatId: routeChatId } = useLocalSearchParams<{ chatId?: string }>();

  const [chatId, setChatId] = useState<string | null>(null);
  const [chatTitle, setChatTitle] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [model, setModel] = useState<string>('auto');
  const [models, setModels] = useState<ModelInfo[]>(DEFAULT_MODELS);
  const [pinned, setPinned] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [menuVisible, setMenuVisible] = useState(false);
  const [renameVisible, setRenameVisible] = useState(false);
  const [renameText, setRenameText] = useState('');
  const [editVisible, setEditVisible] = useState(false);
  const [editText, setEditText] = useState('');
  const [keyboardHeight, setKeyboardHeight] = useState(0);

  const [pendingSend, setPendingSend] = useState<{ text: string; model: string } | null>(null);
  const seededModel = useRef(false);
  const creatingRef = useRef(false);
  const listRef = useRef<FlashListRef<Message>>(null);

  // Poll GET /chats/{id} until a title appears (max 10 s)
  const pollForTitle = useCallback(async (tid: string, cid: string) => {
    for (let i = 0; i < 5; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const updated = await api.getChat(tid, cid);
        if (updated.title) { setChatTitle(updated.title); return; }
      } catch { /* ignore */ }
    }
  }, []);

  const handleFirstReply = useCallback(async () => {
    if (!token || !chatId) return;
    await pollForTitle(token, chatId);
  }, [token, chatId, pollForTitle]);

  const { messages, setMessages, streaming, sendMessage, regenerateResponse, editLastMessage, stopGeneration, connect } =
    useChat(token, chatId, { onFirstReply: handleFirstReply });

  useEffect(() => {
    if (messages.length > 0) {
      listRef.current?.scrollToEnd({ animated: true });
    }
  }, [messages.length, streaming]);

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    const openChatId = typeof routeChatId === 'string' ? routeChatId : null;

    let cancelled = false;
    (async () => {
      // No route chat → a fresh, unsaved chat. The DB row is created lazily on
      // first send (see handleSend), so we never accumulate empty chats.
      if (!openChatId) {
        setChatId(null); setChatTitle(null); setPinned(false); setMessages([]); setLoading(false);
        return;
      }
      setLoading(true);
      try {
        const [chat, existing] = await Promise.all([
          api.getChat(token, openChatId),
          api.listMessages(token, openChatId),
        ]);
        if (cancelled) return;
        setChatId(chat.id); setChatTitle(chat.title); setPinned(chat.pinned);
        setModel(chat.model);
        setMessages(existing);
        // Backend backfills missing titles on list_messages — poll for it
        if (!chat.title && existing.length > 0) {
          pollForTitle(token, openChatId);
        }
      } finally { if (!cancelled) setLoading(false); }
    })();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, routeChatId]);

  useEffect(() => {
    if (token && chatId) connect();
  }, [token, chatId, connect]);

  // Load the model catalog (labels, availability, pricing) for the picker.
  useEffect(() => {
    if (!token) return;
    api.listModels(token).then(setModels).catch(() => {});
  }, [token]);

  // Seed the composer model from the user's saved default (once, on a blank chat)
  useEffect(() => {
    if (seededModel.current) return;
    const def = user?.default_model;
    if (routeChatId == null && def) {
      setModel(def);
      seededModel.current = true;
    }
  }, [user?.default_model, routeChatId]);

  // Once a lazily-created chat is ready, flush the queued first message
  useEffect(() => {
    if (chatId && pendingSend) {
      const { text, model: pendingModel } = pendingSend;
      setPendingSend(null);
      sendMessage(text, pendingModel);
    }
  }, [chatId, pendingSend, sendMessage]);

  useEffect(() => {
    if (messages.length === 0) setMenuVisible(false);
  }, [messages.length]);

  useEffect(() => {
    const showEvent = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
    const hideEvent = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';
    const show = Keyboard.addListener(showEvent, (e) => {
      setKeyboardHeight(e.endCoordinates.height);
      setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 50);
    });
    const hide = Keyboard.addListener(hideEvent, () => setKeyboardHeight(0));
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);

  const lastAssistantId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant' && messages[i].id !== 'streaming') return messages[i].id;
    }
    return null;
  }, [messages]);

  const lastUserId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') return messages[i].id;
    }
    return null;
  }, [messages]);

  const pickerOptions = useMemo(
    () => [AUTO_OPTION, ...models.filter((m) => m.available)],
    [models],
  );
  const currentModel = pickerOptions.find((o) => o.id === model) ?? AUTO_OPTION;

  const startNewChat = useCallback(() => {
    if (streaming) return;
    setInput('');
    setChatId(null); setChatTitle(null); setPinned(false); setMessages([]);
    // Clearing the route param re-runs the loader into the blank state.
    if (routeChatId != null) {
      router.setParams({ chatId: undefined });
    }
  }, [streaming, routeChatId, router, setMessages]);

  // Let the drawer's "New chat" trigger this same action.
  useEffect(() => {
    registerNewChat(startNewChat);
  }, [startNewChat]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || streaming || !token || creatingRef.current) return;
    tap();
    setInput('');
    // Lazily create the chat on the first message of a blank conversation.
    if (!chatId) {
      creatingRef.current = true;
      try {
        const chat = await api.createChat(token, model);
        setChatTitle(null);
        setPendingSend({ text, model });
        setChatId(chat.id);
      } catch {
        setInput(text); // restore the text so the user can retry
      } finally {
        creatingRef.current = false;
      }
      return;
    }
    sendMessage(text, model);
  };

  const handleFeedback = useCallback(
    (messageId: string, next: 'up' | 'down' | null) => {
      setMessages((prev) =>
        prev.map((mm) => (mm.id === messageId ? { ...mm, feedback: next } : mm)),
      );
      // Only persist for real (server-issued) message ids
      const isServerId =
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(messageId);
      if (token && chatId && isServerId) {
        api.setMessageFeedback(token, chatId, messageId, next).catch(() => {});
      }
    },
    [token, chatId, setMessages],
  );

  const closeMenu = () => setMenuVisible(false);

  const openRename = () => { setRenameText(chatTitle ?? ''); setRenameVisible(true); };

  const confirmRename = async () => {
    const title = renameText.trim();
    if (!title || !chatId || !token) { setRenameVisible(false); return; }
    try { const u = await api.renameChat(token, chatId, title); setChatTitle(u.title); } catch { /* ignore */ }
    setRenameVisible(false);
  };

  const openEdit = (text: string) => { setEditText(text); setEditVisible(true); };

  const confirmEdit = () => {
    const text = editText.trim();
    if (!text || streaming) { setEditVisible(false); return; }
    setEditVisible(false);
    editLastMessage(text, model);
  };

  const togglePin = async () => {
    if (!chatId || !token) return;
    tap();
    const next = !pinned;
    setPinned(next);
    try { await api.setPin(token, chatId, next); } catch { setPinned(!next); }
  };

  const confirmDelete = () => {
    Alert.alert('Delete chat', 'This conversation will be permanently removed.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete', style: 'destructive',
        onPress: async () => {
          if (!chatId || !token) return;
          try { await api.deleteChat(token, chatId); } catch { /* ignore */ }
          router.canGoBack() ? router.back() : router.replace('/');
        },
      },
    ]);
  };

  if (!token) return <Redirect href="/login" />;

  if (loading) {
    return <View style={s.center}><Text style={s.loadingDot}>·</Text></View>;
  }

  const headerInset = insets.top + HEADER_BAR_HEIGHT;
  const fadeHeight = headerInset + HEADER_FADE_EXTRA;
  const composerBottomPad = keyboardHeight > 0 ? 8 : Math.max(insets.bottom, 10);
  const listBottomPad = COMPOSER_HEIGHT + composerBottomPad + keyboardHeight;

  return (
    <>
      {/* ··· dropdown menu */}
      <Modal visible={menuVisible} transparent animationType="fade" onRequestClose={closeMenu}>
        <TouchableWithoutFeedback onPress={closeMenu}>
          <View style={drop.overlay}>
            {/* stopPropagation prevents dismiss when tapping inside the card */}
            <TouchableWithoutFeedback onPress={() => {}}>
              <View style={[drop.card, { top: headerInset + 4 }]}>
                <Pressable style={drop.item} onPress={() => { closeMenu(); shareConversation(chatTitle, messages); }}>
                  <Ionicons name="share-outline" size={18} color={C.text} />
                  <Text style={drop.label}>Share</Text>
                </Pressable>
                <View style={drop.divider} />
                <Pressable style={drop.item} onPress={() => { closeMenu(); openRename(); }}>
                  <Ionicons name="pencil-outline" size={18} color={C.text} />
                  <Text style={drop.label}>Rename</Text>
                </Pressable>
                <View style={drop.divider} />
                <Pressable style={drop.item} onPress={() => { closeMenu(); togglePin(); }}>
                  <Ionicons name={pinned ? 'bookmark' : 'bookmark-outline'} size={18} color={C.text} />
                  <Text style={drop.label}>{pinned ? 'Unpin' : 'Pin'}</Text>
                </Pressable>
                <View style={drop.divider} />
                <Pressable style={drop.item} onPress={() => { closeMenu(); confirmDelete(); }}>
                  <Ionicons name="trash-outline" size={18} color={C.danger} />
                  <Text style={[drop.label, drop.labelDanger]}>Delete</Text>
                </Pressable>
              </View>
            </TouchableWithoutFeedback>
          </View>
        </TouchableWithoutFeedback>
      </Modal>

      <Modal visible={renameVisible} transparent animationType="fade" onRequestClose={() => setRenameVisible(false)}>
        <Pressable style={m.overlay} onPress={() => setRenameVisible(false)}>
          <Pressable style={m.sheet} onPress={(e) => e.stopPropagation()}>
            <Text style={m.title}>Rename chat</Text>
            <TextInput
              style={m.input} value={renameText} onChangeText={setRenameText}
              autoFocus returnKeyType="done" onSubmitEditing={confirmRename} maxLength={80} />
            <View style={m.row}>
              <Pressable style={m.cancel} onPress={() => setRenameVisible(false)}>
                <Text style={m.cancelText}>Cancel</Text>
              </Pressable>
              <Pressable style={m.save} onPress={confirmRename}>
                <Text style={m.saveText}>Save</Text>
              </Pressable>
            </View>
          </Pressable>
        </Pressable>
      </Modal>

      <Modal visible={editVisible} transparent animationType="fade" onRequestClose={() => setEditVisible(false)}>
        <Pressable style={m.overlay} onPress={() => setEditVisible(false)}>
          <Pressable style={m.sheet} onPress={(e) => e.stopPropagation()}>
            <Text style={m.title}>Edit message</Text>
            <TextInput
              style={[m.input, { minHeight: 88, textAlignVertical: 'top' }]}
              value={editText} onChangeText={setEditText}
              autoFocus multiline maxLength={4000} />
            <View style={m.row}>
              <Pressable style={m.cancel} onPress={() => setEditVisible(false)}>
                <Text style={m.cancelText}>Cancel</Text>
              </Pressable>
              <Pressable style={m.save} onPress={confirmEdit}>
                <Text style={m.saveText}>Send</Text>
              </Pressable>
            </View>
          </Pressable>
        </Pressable>
      </Modal>

      <View style={s.container}>
          <View style={s.messagesArea}>
            <FlashList
              ref={listRef}
              data={messages}
              style={s.list}
              keyExtractor={(item) => item.id}
              renderItem={({ item }) => (
                <MessageBubble
                  message={item}
                  isLastAssistant={item.id === lastAssistantId}
                  onRegenerate={!streaming && item.id === lastAssistantId ? () => regenerateResponse(model) : undefined}
                  onFeedback={handleFeedback}
                  onEdit={!streaming && item.id === lastUserId ? () => openEdit(item.content) : undefined}
                />
              )}
              contentContainerStyle={[s.listContent, { paddingTop: headerInset, paddingBottom: listBottomPad }]}
              keyboardShouldPersistTaps="handled"
              keyboardDismissMode="interactive"
              ListEmptyComponent={
                <View style={s.empty}>
                  <Ionicons name="chatbubble-ellipses-outline" size={48} color={C.primary} style={{ opacity: 0.5, marginBottom: 12 }} />
                  <Text style={s.emptyTitle}>How can I help?</Text>
                  <Text style={s.emptyHint}>Ask me anything — I'll remember what matters.</Text>
                </View>
              }
            />

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
              style={[s.headerFade, { height: fadeHeight }]}
            />

            {!drawerOpen && (
              <View
                style={[s.header, { paddingTop: insets.top, height: headerInset }]}
                pointerEvents="box-none"
                collapsable={false}
                renderToHardwareTextureAndroid>
                <Pressable style={s.headerBtn} onPress={openDrawer} hitSlop={8}>
                  <Ionicons name="menu-outline" size={24} color={C.primary} />
                </Pressable>
                <View style={{ flex: 1 }} pointerEvents="none" />
                <View style={s.headerRight}>
                  <Pressable style={s.headerBtn} onPress={startNewChat} hitSlop={8}>
                    <Ionicons name="create-outline" size={20} color={C.primary} />
                  </Pressable>
                  {messages.length > 0 && (
                    <Pressable style={s.headerBtn} onPress={() => setMenuVisible((v) => !v)} hitSlop={8}>
                      <Ionicons name="ellipsis-horizontal" size={20} color={C.textSecondary} />
                    </Pressable>
                  )}
                </View>
              </View>
            )}
          </View>

          {!drawerOpen && (
            <View style={[s.composerBlock, { bottom: keyboardHeight, paddingBottom: composerBottomPad }]}>
              {showModelPicker && (
                <View style={s.picker}>
                  {pickerOptions.map((opt) => (
                    <Pressable
                      key={opt.id}
                      style={[s.pickerItem, model === opt.id && s.pickerItemActive]}
                      onPress={() => { setModel(opt.id); setShowModelPicker(false); }}>
                      <View style={[s.modelDot, { backgroundColor: dotColorForTier(opt.tier) }]} />
                      <View style={{ flex: 1 }}>
                        <Text style={[s.pickerLabel, model === opt.id && s.pickerLabelActive]}>{opt.label}</Text>
                        <Text style={s.pickerDesc}>
                          {opt.description}
                          {opt.input_price_per_m != null
                            ? `  ·  $${opt.input_price_per_m}/$${opt.output_price_per_m} per 1M`
                            : ''}
                        </Text>
                      </View>
                      {model === opt.id && <Text style={{ color: C.primary, fontWeight: '700' }}>✓</Text>}
                    </Pressable>
                  ))}
                </View>
              )}

              <View style={s.composer}>
                <View style={s.inputWrap}>
                  <TextInput
                    style={s.input}
                    placeholder="Message Recall..."
                    placeholderTextColor={C.textTertiary}
                    value={input}
                    onChangeText={setInput}
                    multiline
                    returnKeyType="default"
                  />
                  <View style={s.inputRow}>
                    <Pressable style={s.modelPill} onPress={() => setShowModelPicker((v) => !v)}>
                      <View style={[s.modelDot, { backgroundColor: dotColorForTier(currentModel.tier) }]} />
                      <Text style={s.modelPillText}>{currentModel.label}</Text>
                      <Text style={s.modelChevron}>⌄</Text>
                    </Pressable>
                    {streaming ? (
                      <Pressable style={s.sendBtn} onPress={stopGeneration}>
                        <Text style={s.sendIcon}>■</Text>
                      </Pressable>
                    ) : (
                      <Pressable style={[s.sendBtn, !input.trim() && s.sendDim]} onPress={handleSend}>
                        <Text style={s.sendIcon}>↑</Text>
                      </Pressable>
                    )}
                  </View>
                </View>
              </View>
            </View>
          )}
        </View>
    </>
  );
}

const drop = StyleSheet.create({
  overlay: {
    flex: 1,
    // transparent — tap outside card to dismiss
  },
  card: {
    position: 'absolute',
    right: 12,
    backgroundColor: C.bg,
    borderRadius: 14,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
    minWidth: 190,
    shadowColor: '#000',
    shadowOpacity: 0.18,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 6 },
    elevation: 16,
    overflow: 'hidden',
  },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 13,
    gap: 12,
  },
  label: { fontSize: 15, color: C.text, fontWeight: '500' },
  labelDanger: { color: C.danger },
  divider: { height: StyleSheet.hairlineWidth, backgroundColor: C.border, marginHorizontal: 8 },
});

const m = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'center', padding: 24 },
  sheet: { backgroundColor: C.bg, borderRadius: 20, padding: 20, gap: 14 },
  title: { fontSize: 17, fontWeight: '700', color: C.text },
  input: { backgroundColor: C.surface, borderRadius: 12, padding: 12, fontSize: 16, color: C.text, borderWidth: 1.5, borderColor: C.primary },
  row: { flexDirection: 'row', gap: 10 },
  cancel: { flex: 1, borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 12, alignItems: 'center' },
  cancelText: { fontSize: 15, color: C.textSecondary, fontWeight: '600' },
  save: { flex: 1, borderRadius: 12, backgroundColor: C.primary, padding: 12, alignItems: 'center' },
  saveText: { fontSize: 15, color: '#fff', fontWeight: '700' },
});

const s = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: C.bg },
  loadingDot: { fontSize: 48, color: C.primary, opacity: 0.4 },
  container: { flex: 1, backgroundColor: C.bg },
  messagesArea: { flex: 1 },
  headerFade: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 50,
  },
  header: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 100,
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: 8,
    paddingBottom: 8,
    backgroundColor: 'transparent',
  },
  headerBtn: {
    padding: 8,
    borderRadius: 10,
    backgroundColor: C.bg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
    shadowColor: '#000',
    shadowOpacity: 0.1,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 8,
    zIndex: 101,
  },
  headerRight: { flexDirection: 'row', gap: 6, zIndex: 101 },

  list: { flex: 1 },
  listContent: { paddingVertical: 8 },
  empty: { alignItems: 'center', paddingTop: 48, paddingHorizontal: 40 },
  emptyIcon: { fontSize: 32, color: C.primary, marginBottom: 12 },
  emptyTitle: { fontSize: 22, fontWeight: '700', color: C.text, marginBottom: 6 },
  emptyHint: { fontSize: 15, color: C.textSecondary, textAlign: 'center', lineHeight: 22 },

  composerBlock: {
    position: 'absolute',
    left: 0,
    right: 0,
    zIndex: 90,
    backgroundColor: C.bg,
    paddingHorizontal: 12,
    paddingTop: 4,
  },
  composer: {
    paddingVertical: 10,
  },
  inputWrap: {
    backgroundColor: C.surface,
    borderRadius: 22,
    paddingHorizontal: 14,
    paddingTop: 10,
    paddingBottom: 8,
    gap: 6,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  input: { fontSize: 16, color: C.text, maxHeight: 100 },
  modelPill: { flexDirection: 'row', alignItems: 'center', gap: 5, alignSelf: 'flex-start' },
  modelDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: C.primary },
  modelDotPro: { backgroundColor: '#FF9F0A' },
  modelPillText: { fontSize: 13, color: C.textSecondary, fontWeight: '500' },
  modelChevron: { fontSize: 11, color: C.textTertiary },
  sendBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: C.primary, alignItems: 'center', justifyContent: 'center' },
  sendDim: { backgroundColor: '#C4B5FD' },
  sendIcon: { color: '#fff', fontSize: 20, fontWeight: '700' },

  picker: {
    marginBottom: 8,
    backgroundColor: C.bg,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: C.border,
    shadowColor: '#000',
    shadowOpacity: 0.12,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: -4 },
    elevation: 8,
    overflow: 'hidden',
  },
  pickerItem: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingVertical: 14 },
  pickerItemActive: { backgroundColor: C.primaryLight },
  pickerLabel: { fontSize: 15, fontWeight: '600', color: C.text },
  pickerLabelActive: { color: C.primary },
  pickerDesc: { fontSize: 12, color: C.textTertiary, marginTop: 1 },
});
