import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  useWindowDimensions,
  View,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from "react-native";
import { FlashList, FlashListRef } from "@shopify/flash-list";
import { LinearGradient } from "expo-linear-gradient";
import { openDrawer, registerNewChat } from "@/lib/drawer";
import { Redirect, useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Ionicons } from "@expo/vector-icons";

import { Theme, useTheme } from "@/lib/theme";
import { MessageBubble } from "@/components/MessageBubble";
import { SuggestionChips } from "@/components/SuggestionChips";
import { TemplatePicker } from "@/components/TemplatePicker";
import { HamburgerIcon } from "@/components/HamburgerIcon";
import { useAuth } from "@/contexts/AuthContext";
import { useDrawer } from "@/contexts/DrawerContext";
import { useChat } from "@/hooks/useChat";
import { api, Message, ModelInfo } from "@/lib/api";
import { tap } from "@/lib/haptics";
import { shareConversation } from "@/lib/share";
import { MESSAGE_PAGE_SIZE } from "@/lib/chatConstants";

const AUTO_OPTION: ModelInfo = {
  id: "auto",
  label: "Auto",
  provider: "",
  tier: "auto",
  description: "",
  available: true,
  input_price_per_m: null,
  output_price_per_m: null,
};

const DEFAULT_MODELS: ModelInfo[] = [
  {
    id: "free-chat",
    label: "Flash",
    provider: "",
    tier: "fast",
    description: "",
    available: true,
    input_price_per_m: null,
    output_price_per_m: null,
  },
  {
    id: "smart-chat",
    label: "Pro",
    provider: "",
    tier: "smart",
    description: "",
    available: true,
    input_price_per_m: null,
    output_price_per_m: null,
  },
];

function dotColorForTier(tier: string): string {
  if (tier === "smart") return "#FF9F0A";
  if (tier === "max") return "#34C759";
  return "#6C5CE7";
}
const HEADER_BAR_HEIGHT = 52;
const HEADER_FADE_EXTRA = 48;
const COMPOSER_HEIGHT = 100;
const FEEDBACK_ROW_HEIGHT = 48;
const KEYBOARD_LIFT_EXTRA = 0;
const SCROLL_BOTTOM_THRESHOLD = 96;

export default function ChatScreen() {
  const { token, user } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeS(C), [C]);
  const m = useMemo(() => makeM(C), [C]);
  const drop = useMemo(() => makeDrop(C), [C]);
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { height: windowHeight } = useWindowDimensions();
  const drawerOpen = useDrawer().isOpen;
  const { chatId: routeChatId } = useLocalSearchParams<{ chatId?: string }>();

  const [chatId, setChatId] = useState<string | null>(null);
  const [chatTitle, setChatTitle] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [model, setModel] = useState<string>("auto");
  const [models, setModels] = useState<ModelInfo[]>(DEFAULT_MODELS);
  const [pinned, setPinned] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [menuVisible, setMenuVisible] = useState(false);
  const [renameVisible, setRenameVisible] = useState(false);
  const [renameText, setRenameText] = useState("");
  const [keyboardHeight, setKeyboardHeight] = useState(0);
  const [hasMoreOlder, setHasMoreOlder] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);

  const [pendingSend, setPendingSend] = useState<{
    text: string;
    model: string;
    skipUserBubble?: boolean;
  } | null>(null);
  const seededModel = useRef(false);
  const creatingRef = useRef(false);
  const skipLoadForChatIdRef = useRef<string | null>(null);
  const priorRouteChatIdRef = useRef<string | null>(null);
  const listRef = useRef<FlashListRef<Message>>(null);
  const atBottomRef = useRef(true);
  const newMessageCountRef = useRef(0);
  const showScrollBtnRef = useRef(false);
  const messagesLenRef = useRef(0);
  const listBottomPadRef = useRef(0);
  const maxScrollOffsetRef = useRef(0);
  const scrollOffsetRef = useRef(0);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const [scrollAwayCount, setScrollAwayCount] = useState(0);

  const discardEmptyChat = useCallback(
    (id: string | null) => {
      if (!token || !id) return;
      api.deleteChatIfEmpty(token, id).catch(() => {});
    },
    [token],
  );

  // Poll GET /chats/{id} until a title appears (max 10 s)
  const pollForTitle = useCallback(async (tid: string, cid: string) => {
    for (let i = 0; i < 5; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const updated = await api.getChat(tid, cid);
        if (updated.title) {
          setChatTitle(updated.title);
          return;
        }
      } catch {
        /* ignore */
      }
    }
  }, []);

  const handleFirstReply = useCallback(async () => {
    if (!token || !chatId) return;
    await pollForTitle(token, chatId);
  }, [token, chatId, pollForTitle]);

  const handleChatError = useCallback((message: string) => {
    const isQuota = /free limit|daily limit/i.test(message);
    Alert.alert(
      isQuota ? "Free limit reached" : "Could not get a reply",
      message,
    );
  }, []);

  const {
    messages,
    setMessages,
    streaming,
    sendMessage,
    regenerateResponse,
    stopGeneration,
  } = useChat(token, chatId, {
    onFirstReply: handleFirstReply,
    onError: handleChatError,
  });
  messagesLenRef.current = messages.length;

  const updateAtBottom = useCallback((atBottom: boolean) => {
    atBottomRef.current = atBottom;
    const shouldShow = !atBottom && messagesLenRef.current > 0;
    if (shouldShow === showScrollBtnRef.current) return;
    showScrollBtnRef.current = shouldShow;
    setShowScrollToBottom(shouldShow);
    if (!shouldShow) setScrollAwayCount(0);
  }, []);

  const measureFromListRef = useCallback((): boolean | null => {
    const list = listRef.current;
    if (!list) return null;
    try {
      const scrollOffset = list.getAbsoluteLastScrollOffset();
      scrollOffsetRef.current = scrollOffset;
      const contentSize = list.getChildContainerDimensions();
      const windowSize = list.getWindowSize();
      const viewportHeight = windowSize.height;
      const contentHeight = contentSize.height;
      if (viewportHeight <= 0 || contentHeight <= 0) return null;
      const maxOffset = Math.max(0, contentHeight - viewportHeight);
      if (maxOffset > maxScrollOffsetRef.current) {
        maxScrollOffsetRef.current = maxOffset;
      }
      if (maxOffset <= 0) return true;
      const threshold = Math.max(
        SCROLL_BOTTOM_THRESHOLD,
        listBottomPadRef.current * 0.35,
      );
      return maxOffset - scrollOffset <= threshold;
    } catch {
      return null;
    }
  }, []);

  const measureFromScrollEvent = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>): boolean | null => {
      const { contentOffset, contentSize, layoutMeasurement } =
        event.nativeEvent;
      const viewportHeight = layoutMeasurement.height;
      const contentHeight = contentSize.height;
      const scrollY = contentOffset.y;
      scrollOffsetRef.current = scrollY;
      if (viewportHeight <= 0 || contentHeight <= 0) return null;
      const maxOffset = Math.max(0, contentHeight - viewportHeight);
      if (maxOffset > maxScrollOffsetRef.current) {
        maxScrollOffsetRef.current = maxOffset;
      }
      if (maxOffset <= 0) {
        if (maxScrollOffsetRef.current <= 0) return true;
        const threshold = Math.max(
          SCROLL_BOTTOM_THRESHOLD,
          listBottomPadRef.current * 0.35,
        );
        return maxScrollOffsetRef.current - scrollY <= threshold;
      }
      const threshold = Math.max(
        SCROLL_BOTTOM_THRESHOLD,
        listBottomPadRef.current * 0.35,
      );
      return maxOffset - scrollY <= threshold;
    },
    [],
  );

  const measureFromTrackedScroll = useCallback((): boolean | null => {
    if (maxScrollOffsetRef.current <= 0) return null;
    const threshold = Math.max(
      SCROLL_BOTTOM_THRESHOLD,
      listBottomPadRef.current * 0.35,
    );
    return maxScrollOffsetRef.current - scrollOffsetRef.current <= threshold;
  }, []);

  const syncScrollPosition = useCallback(
    (event?: NativeSyntheticEvent<NativeScrollEvent>) => {
      const len = messagesLenRef.current;
      if (len === 0) {
        updateAtBottom(true);
        return;
      }
      const fromRef = measureFromListRef();
      const fromEvent = event ? measureFromScrollEvent(event) : null;
      const fromTrack = measureFromTrackedScroll();
      const results = [fromRef, fromEvent, fromTrack].filter(
        (value): value is boolean => value !== null,
      );
      if (results.length === 0) return;
      // Show the button if any measurement says we're away from the bottom.
      const atBottom = results.every((value) => value);
      updateAtBottom(atBottom);
    },
    [
      measureFromListRef,
      measureFromScrollEvent,
      measureFromTrackedScroll,
      updateAtBottom,
    ],
  );

  // Scroll when a new message appears — but NOT when older messages are
  // prepended during history load (which also changes length).
  useEffect(() => {
    if (messages.length > 0 && newMessageCountRef.current > 0) {
      const pending = newMessageCountRef.current;
      newMessageCountRef.current = 0;
      if (atBottomRef.current) {
        listRef.current?.scrollToEnd({ animated: true });
      } else {
        setScrollAwayCount((c) => c + pending);
        showScrollBtnRef.current = true;
        setShowScrollToBottom(true);
      }
    }
  }, [messages.length]);

  // Follow streaming content growth — scroll without animation so the
  // view stays pinned to the growing text. Only fires when the user is
  // already near the bottom (so we don't yank them away from reading history).
  const streamingLen =
    streaming &&
    messages.length > 0 &&
    messages[messages.length - 1]?.id === "streaming"
      ? messages[messages.length - 1].content.length
      : 0;
  useEffect(() => {
    if (streamingLen && atBottomRef.current) {
      listRef.current?.scrollToEnd({ animated: false });
    } else if (streamingLen) {
      requestAnimationFrame(() => syncScrollPosition());
    }
  }, [streamingLen, syncScrollPosition]);

  useEffect(() => {
    requestAnimationFrame(() => syncScrollPosition());
  }, [messages.length, syncScrollPosition]);

  useEffect(() => {
    maxScrollOffsetRef.current = 0;
    scrollOffsetRef.current = 0;
    showScrollBtnRef.current = false;
    setShowScrollToBottom(false);
    setScrollAwayCount(0);
    atBottomRef.current = true;
  }, [chatId]);

  const scrollToLatest = useCallback(() => {
    tap();
    listRef.current?.scrollToEnd({ animated: true });
    updateAtBottom(true);
  }, [updateAtBottom]);

  const handleScroll = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      syncScrollPosition(event);
    },
    [syncScrollPosition],
  );

  const handleScrollEnd = useCallback(() => {
    syncScrollPosition();
  }, [syncScrollPosition]);

  useEffect(() => {
    const showEvent =
      Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow";
    const hideEvent =
      Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide";

    const show = Keyboard.addListener(showEvent, (e) => {
      setKeyboardHeight(Math.max(0, windowHeight - e.endCoordinates.screenY));
      setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 50);
    });
    const hide = Keyboard.addListener(hideEvent, () => setKeyboardHeight(0));
    return () => {
      show.remove();
      hide.remove();
    };
  }, [windowHeight]);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    const openChatId = typeof routeChatId === "string" ? routeChatId : null;
    const prevOpenChatId = priorRouteChatIdRef.current;
    if (prevOpenChatId && prevOpenChatId !== openChatId) {
      discardEmptyChat(prevOpenChatId);
    }
    priorRouteChatIdRef.current = openChatId;

    let cancelled = false;
    (async () => {
      // No route chat → a fresh, unsaved chat. The DB row is created lazily on
      // first send (see handleSend), so we never accumulate empty chats.
      if (!openChatId) {
        setLoading(false);
        if (!creatingRef.current) {
          setChatId(null);
          setChatTitle(null);
          setPinned(false);
          setMessages([]);
          setHasMoreOlder(false);
        }
        return;
      }
      if (skipLoadForChatIdRef.current === openChatId) {
        skipLoadForChatIdRef.current = null;
        setChatId(openChatId);
        setLoading(false);
        return;
      }
      setLoading(true);
      setHasMoreOlder(false);
      try {
        const [chat, page] = await Promise.all([
          api.getChat(token, openChatId),
          api.listMessages(token, openChatId, { limit: MESSAGE_PAGE_SIZE }),
        ]);
        if (cancelled) return;
        setChatId(chat.id);
        setChatTitle(chat.title);
        setPinned(chat.pinned);
        setModel(chat.model);
        setMessages(page.messages);
        setHasMoreOlder(page.has_more);
        // Backend backfills missing titles on list_messages — poll for it
        if (!chat.title && page.messages.length > 0) {
          pollForTitle(token, openChatId);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, routeChatId]);

  // Load the model catalog (labels, availability, pricing) for the picker.
  useEffect(() => {
    if (!token) return;
    api
      .listModels(token)
      .then(setModels)
      .catch(() => {});
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
      const { text, model: pendingModel, skipUserBubble } = pendingSend;
      setPendingSend(null);
      sendMessage(text, pendingModel, { skipUserBubble });
    }
  }, [chatId, pendingSend, sendMessage]);

  useEffect(() => {
    if (messages.length === 0) setMenuVisible(false);
  }, [messages.length]);

  const lastAssistantId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return messages[i].id;
    }
    return null;
  }, [messages]);

  const loadOlderMessages = useCallback(async () => {
    if (
      !token ||
      !chatId ||
      loadingOlder ||
      !hasMoreOlder ||
      messages.length === 0
    )
      return;
    const oldest = messages[0];
    const isServerId =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
        oldest.id,
      );
    if (!isServerId) return;

    setLoadingOlder(true);
    try {
      const page = await api.listMessages(token, chatId, {
        limit: MESSAGE_PAGE_SIZE,
        before: oldest.id,
      });
      setMessages((prev) => [...page.messages, ...prev]);
      setHasMoreOlder(page.has_more);
    } catch {
      /* ignore */
    } finally {
      setLoadingOlder(false);
    }
  }, [token, chatId, loadingOlder, hasMoreOlder, messages]);

  const pickerOptions = useMemo(
    () => [AUTO_OPTION, ...models.filter((m) => m.available)],
    [models],
  );
  const currentModel = pickerOptions.find((o) => o.id === model) ?? AUTO_OPTION;

  const startNewChat = useCallback(() => {
    if (streaming) return;
    discardEmptyChat(chatId);
    setInput("");
    setChatId(null);
    setChatTitle(null);
    setPinned(false);
    setMessages([]);
    setHasMoreOlder(false);
    // Clearing the route param re-runs the loader into the blank state.
    if (routeChatId != null) {
      router.setParams({ chatId: undefined });
    }
  }, [streaming, chatId, discardEmptyChat, routeChatId, router, setMessages]);

  // Let the drawer's "New chat" trigger this same action.
  useEffect(() => {
    registerNewChat(startNewChat);
  }, [startNewChat]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || streaming || !token || creatingRef.current) return;
    tap();
    setInput("");
    newMessageCountRef.current += 1;
    // Lazily create the chat on the first message of a blank conversation.
    if (!chatId) {
      creatingRef.current = true;
      const optimisticId = `local-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        {
          id: optimisticId,
          role: "user",
          content: text,
          model: model ?? null,
          created_at: new Date().toISOString(),
        },
      ]);
      try {
        const chat = await api.createChat(token, model);
        skipLoadForChatIdRef.current = chat.id;
        setChatTitle(null);
        setChatId(chat.id);
        router.setParams({ chatId: chat.id });
        setPendingSend({ text, model, skipUserBubble: true });
      } catch {
        setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
        setInput(text);
      } finally {
        creatingRef.current = false;
      }
      return;
    }
    newMessageCountRef.current += 1;
    sendMessage(text, model);
  };

  const handleFeedback = useCallback(
    (messageId: string, next: "up" | "down" | null) => {
      setMessages((prev) =>
        prev.map((mm) =>
          mm.id === messageId ? { ...mm, feedback: next } : mm,
        ),
      );
      // Only persist for real (server-issued) message ids
      const isServerId =
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
          messageId,
        );
      if (token && chatId && isServerId) {
        api.setMessageFeedback(token, chatId, messageId, next).catch(() => {});
      }
    },
    [token, chatId, setMessages],
  );

  const closeMenu = () => setMenuVisible(false);

  const renderItem = useCallback(
    ({ item }: { item: Message }) => (
      <MessageBubble
        message={item}
        isGenerating={streaming && item.id === "streaming"}
        isLastAssistant={
          item.role === "assistant" && item.id === lastAssistantId
        }
        onRegenerate={
          item.role === "assistant" &&
          item.id === lastAssistantId &&
          !streaming
            ? () => regenerateResponse(model)
            : undefined
        }
        onFeedback={handleFeedback}
      />
    ),
    [streaming, lastAssistantId, model, regenerateResponse, handleFeedback],
  );

  const openRename = () => {
    setRenameText(chatTitle ?? "");
    setRenameVisible(true);
  };

  const confirmRename = async () => {
    const title = renameText.trim();
    if (!title || !chatId || !token) {
      setRenameVisible(false);
      return;
    }
    try {
      const u = await api.renameChat(token, chatId, title);
      setChatTitle(u.title);
    } catch {
      /* ignore */
    }
    setRenameVisible(false);
  };

  const togglePin = async () => {
    if (!chatId || !token) return;
    tap();
    const next = !pinned;
    setPinned(next);
    try {
      await api.setPin(token, chatId, next);
    } catch {
      setPinned(!next);
    }
  };

  const confirmDelete = () => {
    Alert.alert(
      t("chat.delete_confirm_title"),
      t("chat.delete_confirm_body"),
      [
        { text: t("common.cancel"), style: "cancel" },
        {
          text: t("common.delete"),
          style: "destructive",
          onPress: async () => {
            if (!chatId || !token) return;
            try {
              await api.deleteChat(token, chatId);
            } catch {
              /* ignore */
            }
            router.canGoBack() ? router.back() : router.replace("/");
          },
        },
      ],
    );
  };

  if (!token) return <Redirect href="/login" />;

  if (loading) {
    return (
      <View style={s.center}>
        <Text style={s.loadingDot}>·</Text>
      </View>
    );
  }

  const headerInset = insets.top + HEADER_BAR_HEIGHT;
  const fadeHeight = headerInset + HEADER_FADE_EXTRA;
  const composerLift =
    keyboardHeight > 0 ? keyboardHeight + KEYBOARD_LIFT_EXTRA : 0;
  const composerBottomPad =
    keyboardHeight > 0 ? 0 : Math.max(insets.bottom, 10);
  const composerClearance = COMPOSER_HEIGHT + composerBottomPad + composerLift;
  const listBottomPad =
    COMPOSER_HEIGHT +
    composerBottomPad +
    composerLift +
    (messages.length > 0 && !streaming ? FEEDBACK_ROW_HEIGHT : 0);
  listBottomPadRef.current = listBottomPad;
  const emptyHeight = Math.max(
    160,
    windowHeight - headerInset - composerClearance,
  );

  return (
    <>
      {/* ··· dropdown menu */}
      <Modal
        visible={menuVisible}
        transparent
        animationType="fade"
        onRequestClose={closeMenu}
      >
        <TouchableWithoutFeedback onPress={closeMenu}>
          <View style={drop.overlay}>
            {/* stopPropagation prevents dismiss when tapping inside the card */}
            <TouchableWithoutFeedback onPress={() => {}}>
              <View style={[drop.card, { top: headerInset + 4 }]}>
                <Pressable
                  style={drop.item}
                  onPress={async () => {
                    closeMenu();
                    if (!token || !chatId) {
                      await shareConversation(chatTitle, messages);
                      return;
                    }
                    try {
                      const all = await api.listAllMessages(token, chatId);
                      await shareConversation(chatTitle, all);
                    } catch {
                      await shareConversation(chatTitle, messages);
                    }
                  }}
                >
                  <Ionicons name="share-outline" size={18} color={C.text} />
                  <Text style={drop.label}>{t("chat.share")}</Text>
                </Pressable>
                <View style={drop.divider} />
                <Pressable
                  style={drop.item}
                  onPress={() => {
                    closeMenu();
                    openRename();
                  }}
                >
                  <Ionicons name="pencil-outline" size={18} color={C.text} />
                  <Text style={drop.label}>{t("chat.rename")}</Text>
                </Pressable>
                <View style={drop.divider} />
                <Pressable
                  style={drop.item}
                  onPress={() => {
                    closeMenu();
                    togglePin();
                  }}
                >
                  <Ionicons
                    name={pinned ? "bookmark" : "bookmark-outline"}
                    size={18}
                    color={C.text}
                  />
                  <Text style={drop.label}>{pinned ? t("chat.unpin") : t("chat.pin")}</Text>
                </Pressable>
                <View style={drop.divider} />
                <Pressable
                  style={drop.item}
                  onPress={() => {
                    closeMenu();
                    confirmDelete();
                  }}
                >
                  <Ionicons name="trash-outline" size={18} color={C.danger} />
                  <Text style={[drop.label, drop.labelDanger]}>{t("common.delete")}</Text>
                </Pressable>
              </View>
            </TouchableWithoutFeedback>
          </View>
        </TouchableWithoutFeedback>
      </Modal>

      <Modal
        visible={renameVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setRenameVisible(false)}
      >
        <Pressable style={m.overlay} onPress={() => setRenameVisible(false)}>
          <Pressable style={m.sheet} onPress={(e) => e.stopPropagation()}>
            <Text style={m.title}>{t("chat.rename_title")}</Text>
            <TextInput
              style={m.input}
              value={renameText}
              onChangeText={setRenameText}
              autoFocus
              returnKeyType="done"
              onSubmitEditing={confirmRename}
              maxLength={80}
            />
            <View style={m.row}>
              <Pressable
                style={m.cancel}
                onPress={() => setRenameVisible(false)}
              >
                <Text style={m.cancelText}>{t("common.cancel")}</Text>
              </Pressable>
              <Pressable style={m.save} onPress={confirmRename}>
                <Text style={m.saveText}>{t("settings.save")}</Text>
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
            drawDistance={280}
            maintainVisibleContentPosition={{
              disabled: false,
              autoscrollToBottomThreshold: 0.1,
              startRenderingFromBottom: true,
            }}
            keyExtractor={(item) => item.id}
            getItemType={(item) => item.role}
            renderItem={renderItem}
            onScroll={handleScroll}
            onScrollEndDrag={handleScrollEnd}
            onMomentumScrollEnd={handleScrollEnd}
            scrollEventThrottle={16}
            contentContainerStyle={[
              s.listContent,
              { paddingTop: headerInset, paddingBottom: listBottomPad },
            ]}
            keyboardShouldPersistTaps="handled"
            keyboardDismissMode="interactive"
            ListHeaderComponent={
              hasMoreOlder ? (
                <Pressable
                  style={s.loadEarlier}
                  onPress={loadOlderMessages}
                  disabled={loadingOlder}
                  accessibilityRole="button"
                  accessibilityLabel={t("chat.load_earlier")}
                >
                  <Text style={s.loadEarlierText}>
                    {loadingOlder ? "…" : t("chat.load_earlier")}
                  </Text>
                </Pressable>
              ) : null
            }
            ListEmptyComponent={
              <View style={[s.empty, { height: emptyHeight }]}>
                {token ? (
                  <SuggestionChips
                    token={token}
                    onSelect={(text) => {
                      setInput(text);
                      // Use requestAnimationFrame to let state flush, then send.
                      requestAnimationFrame(() => {
                        handleSend();
                      });
                    }}
                  />
                ) : null}
                <Ionicons
                  name="chatbubble-ellipses-outline"
                  size={48}
                  color={C.primary}
                  style={s.emptyIcon}
                />
                <Text style={s.emptyTitle}>{t("chat.empty_title")}</Text>
                <Text style={s.emptyHint}>
                  {t("chat.empty_hint")}
                </Text>
                {token ? (
                  <TemplatePicker
                    token={token}
                    onSelect={(content) => setInput(content)}
                  />
                ) : null}
              </View>
            }
          />

          <LinearGradient
            colors={[C.bg, C.bg, `${C.bg}00`]}
            locations={[0, 0.55, 1]}
            style={[s.headerFade, { height: fadeHeight }]}
            pointerEvents="none"
          />

          {!drawerOpen && (
            <View
              style={[
                s.header,
                { paddingTop: insets.top, height: headerInset },
              ]}
              pointerEvents="box-none"
              collapsable={false}
              renderToHardwareTextureAndroid
            >
              <Pressable style={s.headerBtn} onPress={openDrawer} hitSlop={12}>
                <HamburgerIcon size={22} color={C.text} />
              </Pressable>
              <View style={s.headerSpacer} />
              <View style={s.headerRight}>
                <Pressable
                  style={s.headerBtn}
                  onPress={startNewChat}
                  hitSlop={12}
                >
                  <Ionicons name="create-outline" size={22} color={C.text} />
                </Pressable>
                {messages.length > 0 && (
                  <Pressable
                    style={s.headerBtn}
                    onPress={() => setMenuVisible((v) => !v)}
                    hitSlop={12}
                  >
                    <Ionicons
                      name="ellipsis-vertical"
                      size={22}
                      color={C.text}
                    />
                  </Pressable>
                )}
              </View>
            </View>
          )}
        </View>

        {!drawerOpen && showScrollToBottom && (
          <View
            style={[s.scrollOverlay, { bottom: composerClearance + 8 }]}
            pointerEvents="box-none"
          >
            <Pressable
              style={s.scrollToBottom}
              onPress={scrollToLatest}
              accessibilityRole="button"
              accessibilityLabel="Scroll to latest messages"
            >
              <Ionicons name="chevron-down" size={22} color={C.text} />
              {scrollAwayCount > 0 ? (
                <View style={s.scrollToBottomBadge}>
                  <Text style={s.scrollToBottomBadgeText}>
                    {scrollAwayCount > 9 ? "9+" : scrollAwayCount}
                  </Text>
                </View>
              ) : null}
            </Pressable>
          </View>
        )}

        {showModelPicker && !drawerOpen && (
          <Pressable
            style={s.pickerBackdrop}
            onPress={() => setShowModelPicker(false)}
            accessibilityLabel="Close model picker"
          />
        )}

        {!drawerOpen && (
          <View
            style={[
              s.composerBlock,
              { bottom: composerLift, paddingBottom: composerBottomPad },
            ]}
          >
            {showModelPicker && (
              <View style={s.picker}>
                {pickerOptions.map((opt) => (
                  <Pressable
                    key={opt.id}
                    style={[
                      s.pickerItem,
                      model === opt.id && s.pickerItemActive,
                    ]}
                    onPress={() => {
                      setModel(opt.id);
                      setShowModelPicker(false);
                    }}
                  >
                    <View
                      style={[
                        s.modelDot,
                        { backgroundColor: dotColorForTier(opt.tier) },
                      ]}
                    />
                    <Text
                      style={[
                        s.pickerLabel,
                        model === opt.id && s.pickerLabelActive,
                        { flex: 1 },
                      ]}
                    >
                      {opt.label}
                    </Text>
                    {model === opt.id && <Text style={s.pickerCheck}>✓</Text>}
                  </Pressable>
                ))}
              </View>
            )}

            <View style={s.composer}>
              <View style={s.inputWrap}>
                <View style={s.inputRowMain}>
                  <TextInput
                    style={s.input}
                    placeholder={t("chat.placeholder")}
                    placeholderTextColor={C.textTertiary}
                    value={input}
                    onChangeText={setInput}
                    onFocus={() => setShowModelPicker(false)}
                    multiline
                    returnKeyType="default"
                  />
                  <View style={s.sendBtnSlot}>
                    {streaming ? (
                      <Pressable style={s.sendBtn} onPress={stopGeneration}>
                        <Text style={s.sendIcon}>■</Text>
                      </Pressable>
                    ) : input.trim() ? (
                      <Pressable style={s.sendBtn} onPress={handleSend}>
                        <Text style={s.sendIcon}>↑</Text>
                      </Pressable>
                    ) : null}
                  </View>
                </View>
                <Pressable
                  style={s.modelPill}
                  onPress={() => setShowModelPicker((v) => !v)}
                  hitSlop={6}
                >
                  <View
                    style={[
                      s.modelDot,
                      { backgroundColor: dotColorForTier(currentModel.tier) },
                    ]}
                  />
                  <Text style={s.modelPillText}>{currentModel.label}</Text>
                  <Ionicons
                    name={showModelPicker ? "chevron-up" : "chevron-down"}
                    size={12}
                    color={C.textTertiary}
                  />
                </Pressable>
              </View>
            </View>
          </View>
        )}
      </View>
    </>
  );
}

const makeDrop = (C: Theme) => StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.06)",
  },
  card: {
    position: "absolute",
    right: 12,
    backgroundColor: C.bg,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#D1D1D6",
    minWidth: 190,
    overflow: "hidden",
  },
  item: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 12,
  },
  label: { fontSize: 16, color: C.text, fontWeight: "400" },
  labelDanger: { color: C.danger },
  divider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: C.border,
    marginHorizontal: 8,
  },
});

const makeM = (C: Theme) => StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.4)",
    justifyContent: "center",
    padding: 24,
  },
  sheet: { backgroundColor: C.bg, borderRadius: 20, padding: 20, gap: 14 },
  title: { fontSize: 17, fontWeight: "700", color: C.text },
  input: {
    backgroundColor: C.surface,
    borderRadius: 12,
    padding: 12,
    fontSize: 16,
    color: C.text,
    borderWidth: 1.5,
    borderColor: C.primary,
  },
  row: { flexDirection: "row", gap: 10 },
  cancel: {
    flex: 1,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    padding: 12,
    alignItems: "center",
  },
  cancelText: { fontSize: 15, color: C.textSecondary, fontWeight: "600" },
  save: {
    flex: 1,
    borderRadius: 12,
    backgroundColor: C.primary,
    padding: 12,
    alignItems: "center",
  },
  saveText: { fontSize: 15, color: "#fff", fontWeight: "700" },
});

const makeS = (C: Theme) => StyleSheet.create({
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: C.bg,
  },
  loadingDot: { fontSize: 48, color: C.primary, opacity: 0.4 },
  container: { flex: 1, backgroundColor: C.bg },
  messagesArea: { flex: 1 },
  headerFade: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    zIndex: 50,
  },
  header: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    zIndex: 100,
    flexDirection: "row",
    alignItems: "flex-end",
    paddingHorizontal: 4,
    paddingBottom: 4,
    backgroundColor: "transparent",
  },
  headerBtn: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 10,
    backgroundColor: C.bg,
    zIndex: 101,
  },
  headerRight: { flexDirection: "row", alignItems: "center", zIndex: 101 },

  list: { flex: 1 },
  scrollOverlay: {
    position: "absolute",
    left: 0,
    right: 0,
    alignItems: "center",
    zIndex: 95,
  },
  scrollToBottom: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: C.bg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
    alignItems: "center",
    justifyContent: "center",
    boxShadow: "0 2 10 0 rgba(0, 0, 0, 0.18)",
    elevation: 8,
  },
  scrollToBottomBadge: {
    position: "absolute",
    top: -4,
    right: -4,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    paddingHorizontal: 4,
    backgroundColor: C.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  scrollToBottomBadgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#fff",
  },
  listContent: { paddingVertical: 8 },
  loadEarlier: {
    alignSelf: "center",
    marginVertical: 10,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: C.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
  },
  loadEarlierText: { fontSize: 14, fontWeight: "600", color: C.primary },
  empty: {
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 40,
  },
  emptyIcon: { opacity: 0.5, marginBottom: 12 },
  headerSpacer: { flex: 1, pointerEvents: "none" as const },
  emptyTitle: {
    fontSize: 22,
    fontWeight: "700",
    color: C.text,
    marginBottom: 6,
  },
  emptyHint: {
    fontSize: 15,
    color: C.textSecondary,
    textAlign: "center",
    lineHeight: 22,
  },

  pickerBackdrop: {
    ...StyleSheet.absoluteFill,
    zIndex: 80,
  },

  composerBlock: {
    position: "absolute",
    left: 0,
    right: 0,
    zIndex: 90,
    backgroundColor: C.bg,
    paddingHorizontal: 12,
    paddingTop: 2,
  },
  composer: {
    paddingVertical: 6,
  },
  inputWrap: {
    backgroundColor: C.surface,
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingTop: 8,
    paddingBottom: 6,
  },
  inputRowMain: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 8,
  },
  input: {
    flex: 1,
    fontSize: 16,
    color: C.text,
    maxHeight: 100,
    paddingVertical: 0,
    minHeight: 22,
  },
  modelPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    alignSelf: "flex-start",
    marginTop: 6,
    paddingVertical: 2,
    paddingRight: 2,
  },
  modelDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: C.primary,
  },
  modelDotPro: { backgroundColor: "#FF9F0A" },
  modelPillText: { fontSize: 12, color: C.textSecondary, fontWeight: "500" },
  sendBtn: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: C.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  sendBtnSlot: {
    width: 34,
    height: 35,
    alignItems: "center",
    justifyContent: "flex-end",
  },
  sendIcon: { color: "#fff", fontSize: 18, fontWeight: "700" },

  picker: {
    marginBottom: 8,
    backgroundColor: C.bg,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: C.border,
    boxShadow: "0 -4 12 0 rgba(0, 0, 0, 0.12)",
    elevation: 8,
    overflow: "hidden",
  },
  pickerItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  pickerItemActive: { backgroundColor: C.primaryLight },
  pickerLabel: { fontSize: 15, fontWeight: "600", color: C.text },
  pickerLabelActive: { color: C.primary },
  pickerCheck: { color: C.primary, fontWeight: "700", fontSize: 15 },
});
