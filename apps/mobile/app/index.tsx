import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  InteractionManager,
  Keyboard,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from "react-native";
import { FlashList, FlashListRef } from "@shopify/flash-list";
import { LinearGradient } from "expo-linear-gradient";
import { openDrawer, registerNewChat } from "@/lib/drawer";
import { Redirect, useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Ionicons } from "@expo/vector-icons";

import { Theme, useTheme } from "@/lib/theme";
import { SuggestedRemindersNudge } from "@/components/SuggestedRemindersNudge";
import { MessageBubble } from "@/components/MessageBubble";
import { HomeStarters } from "@/components/HomeStarters";
import { HamburgerIcon } from "@/components/HamburgerIcon";
import { ChatActionsSheet } from "@/components/ChatActionsSheet";
import { ChatRenameSheet } from "@/components/ChatRenameSheet";
import { ActionBanner } from "@/components/ActionBanner";
import { StateView } from "@/components/StateView";
import { DrawerShell } from "@/components/DrawerShell";
import { useAuth } from "@/contexts/AuthContext";
import { useDrawer } from "@/contexts/DrawerContext";
import { useChat } from "@/hooks/useChat";
import { useModels } from "@/hooks/useModels";
import { UpgradeSheet } from "@/components/UpgradeSheet";
import { AttachmentSourceSheet } from "@/components/AttachmentSourceSheet";
import type { AttachmentSource } from "@/components/AttachmentSourceSheet";
import { ComposerAttachmentPreview } from "@/components/ComposerAttachmentPreview";
import { ReminderBadge } from "@/components/ReminderBadge";
import { api, Message } from "@/lib/api";
import { tap } from "@/lib/haptics";
import { shareConversation } from "@/lib/share";
import { MESSAGE_PAGE_SIZE } from "@/lib/chatConstants";
import { takeQueuedChatLaunch, type QueuedChatLaunch } from "@/lib/chatLaunch";
import { useReminderBadgeCount } from "@/hooks/useReminderBadgeCount";
import {
  messageTextForSend,
  pickDocument,
  pickFromCamera,
  pickFromPhotoLibrary,
  uploadChatAttachment,
  type PendingAttachment,
} from "@/lib/attachments";
import { parseUserMessageContent } from "@/lib/messageAttachments";

const HEADER_BAR_HEIGHT = 52;
const HEADER_FADE_EXTRA = 48;
const COMPOSER_HEIGHT = 100;
const COMPOSER_IMAGE_PREVIEW_EXTRA = 84;
const COMPOSER_FILE_PREVIEW_EXTRA = 44;

function composerAttachmentExtra(attachment: PendingAttachment | null): number {
  if (!attachment) return 0;
  return attachment.kind === "image" ? COMPOSER_IMAGE_PREVIEW_EXTRA : COMPOSER_FILE_PREVIEW_EXTRA;
}
const FEEDBACK_ROW_HEIGHT = 48;
const KEYBOARD_LIFT_EXTRA = 0;
const SCROLL_HIDE_AT_BOTTOM = 64;
const SCROLL_SHOW_MIN_AWAY = 280;
const SCROLL_SHOW_VIEWPORT_RATIO = 0.28;

function ChatScreen() {
  const { token, user } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeS(C), [C]);
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { height: windowHeight } = useWindowDimensions();
  const drawerOpen = useDrawer().isOpen;
  const { chatId: routeChatId, prompt: routePrompt, launchId: routeLaunchId } =
    useLocalSearchParams<{ chatId?: string; prompt?: string; launchId?: string }>();

  const [chatId, setChatId] = useState<string | null>(null);
  const [draftChatId, setDraftChatId] = useState<string | null>(null);
  const draftChatIdRef = useRef<string | null>(null);
  const draftProjectIdRef = useRef<string | null>(null);
  const draftCreatePromiseRef = useRef<Promise<string | null> | null>(null);
  const [chatTitle, setChatTitle] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [pendingAttachment, setPendingAttachment] = useState<PendingAttachment | null>(null);
  const [attachBusy, setAttachBusy] = useState(false);
  const [attachSheetOpen, setAttachSheetOpen] = useState(false);
  const attachPickInFlightRef = useRef(false);
  const { isPro } = useModels();
  const { unseenCount, showIndicator } = useReminderBadgeCount({ enabled: Boolean(token) });
  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const [showPlanPicker, setShowPlanPicker] = useState(false);
  const [menuVisible, setMenuVisible] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const [renameVisible, setRenameVisible] = useState(false);
  const [renameText, setRenameText] = useState("");
  const [keyboardHeight, setKeyboardHeight] = useState(0);
  const [hasMoreOlder, setHasMoreOlder] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);

  const [pendingSend, setPendingSend] = useState<{
    text: string;
    skipUserBubble?: boolean;
    attachmentIds?: string[];
    localImageUri?: string | null;
  } | null>(null);
  const [pendingLaunch, setPendingLaunch] = useState<string | null>(null);
  const pendingLaunchRef = useRef<string | null>(null);
  const pendingProjectIdRef = useRef<string | null>(null);
  const creatingRef = useRef(false);
  const skipLoadForChatIdRef = useRef<string | null>(null);
  const handledLaunchIdRef = useRef<string | null>(null);
  const priorRouteChatIdRef = useRef<string | null>(null);
  const listRef = useRef<FlashListRef<Message>>(null);
  const atBottomRef = useRef(true);
  const newMessageCountRef = useRef(0);
  const showScrollBtnRef = useRef(false);
  const messagesLenRef = useRef(0);
  const listBottomPadRef = useRef(0);
  const maxScrollOffsetRef = useRef(0);
  const scrollOffsetRef = useRef(0);
  const viewportHeightRef = useRef(0);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const [scrollAwayCount, setScrollAwayCount] = useState(0);
  const [actionBanner, setActionBanner] = useState<{
    message: string;
    icon?: keyof typeof Ionicons.glyphMap;
  } | null>(null);

  const discardEmptyChat = useCallback(
    (id: string | null) => {
      if (!token || !id) return;
      api.deleteChatIfEmpty(token, id).catch(() => {});
    },
    [token],
  );

  const clearDraftChat = useCallback(
    (id?: string | null) => {
      const toDiscard = id ?? draftChatIdRef.current;
      draftChatIdRef.current = null;
      draftProjectIdRef.current = null;
      draftCreatePromiseRef.current = null;
      setDraftChatId(null);
      if (toDiscard && token) {
        api.deleteChat(token, toDiscard).catch(() => {});
      }
    },
    [token],
  );

  const prepareDraftChat = useCallback(
    async (projectId?: string | null): Promise<string | null> => {
    if (!token) return null;
    if (chatId) return chatId;
    if (draftChatIdRef.current) return draftChatIdRef.current;
    if (draftCreatePromiseRef.current) return draftCreatePromiseRef.current;

    const resolvedProjectId = projectId ?? draftProjectIdRef.current ?? undefined;
    if (resolvedProjectId) {
      draftProjectIdRef.current = resolvedProjectId;
    }

    const task = api
      .createChat(token, "auto", resolvedProjectId)
      .then((chat) => {
        draftChatIdRef.current = chat.id;
        setDraftChatId(chat.id);
        return chat.id;
      })
      .catch(() => null)
      .finally(() => {
        draftCreatePromiseRef.current = null;
      });
    draftCreatePromiseRef.current = task;
    return task;
  },
    [token, chatId],
  );

  const activeChatId = chatId ?? draftChatId;

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

  const handleChatError = useCallback(
    (message: string) => {
      const isQuota = /free limit|daily limit/i.test(message);
      Alert.alert(
        isQuota ? t("chat.quota_title") : t("chat.error_title"),
        message,
      );
    },
    [t],
  );

  const {
    messages,
    setMessages,
    streaming,
    sendMessage,
    regenerateResponse,
    editMessage,
    stopGeneration,
    connect,
  } = useChat(token, activeChatId, {
    onFirstReply: handleFirstReply,
    onError: handleChatError,
  });
  messagesLenRef.current = messages.length;

  // Pre-create an empty chat + warm the WebSocket while the home screen is visible.
  useEffect(() => {
    if (!token || routeChatId || chatId || messages.length > 0 || streaming) return;
    void prepareDraftChat();
  }, [token, routeChatId, chatId, messages.length, streaming, prepareDraftChat]);

  useEffect(() => {
    if (!token || !draftChatId || chatId || streaming) return;
    void connect();
  }, [token, draftChatId, chatId, streaming, connect]);

  const updateAtBottom = useCallback((atBottom: boolean) => {
    atBottomRef.current = atBottom;
    const shouldShow = !atBottom && messagesLenRef.current > 0;
    if (shouldShow === showScrollBtnRef.current) return;
    showScrollBtnRef.current = shouldShow;
    setShowScrollToBottom(shouldShow);
    if (!shouldShow) setScrollAwayCount(0);
  }, []);

  const measureScrollMetrics = useCallback(
    (event?: NativeSyntheticEvent<NativeScrollEvent>): {
      distanceFromBottom: number;
      maxOffset: number;
    } | null => {
      if (event) {
        const { contentOffset, contentSize, layoutMeasurement } =
          event.nativeEvent;
        const viewportHeight = layoutMeasurement.height;
        const contentHeight = contentSize.height;
        const scrollY = contentOffset.y;
        scrollOffsetRef.current = scrollY;
        if (viewportHeight > 0) viewportHeightRef.current = viewportHeight;
        if (viewportHeight <= 0 || contentHeight <= 0) return null;
        const maxOffset = Math.max(0, contentHeight - viewportHeight);
        maxScrollOffsetRef.current = maxOffset;
        return { distanceFromBottom: maxOffset - scrollY, maxOffset };
      }

      const list = listRef.current;
      if (!list) return null;
      try {
        const scrollOffset = list.getAbsoluteLastScrollOffset();
        scrollOffsetRef.current = scrollOffset;
        const contentSize = list.getChildContainerDimensions();
        const windowSize = list.getWindowSize();
        const viewportHeight = windowSize.height;
        const contentHeight = contentSize.height;
        if (viewportHeight > 0) viewportHeightRef.current = viewportHeight;
        if (viewportHeight <= 0 || contentHeight <= 0) return null;
        const maxOffset = Math.max(0, contentHeight - viewportHeight);
        maxScrollOffsetRef.current = maxOffset;
        return { distanceFromBottom: maxOffset - scrollOffset, maxOffset };
      } catch {
        return null;
      }
    },
    [],
  );

  const getScrollThresholds = useCallback(() => {
    const viewport = viewportHeightRef.current || windowHeight * 0.55;
    const hideAtBottom = Math.max(
      SCROLL_HIDE_AT_BOTTOM,
      listBottomPadRef.current * 0.2,
    );
    const showWhenAway = Math.max(
      SCROLL_SHOW_MIN_AWAY,
      viewport * SCROLL_SHOW_VIEWPORT_RATIO,
      listBottomPadRef.current * 0.55,
    );
    return { hideAtBottom, showWhenAway };
  }, [windowHeight]);

  const syncScrollPosition = useCallback(
    (event?: NativeSyntheticEvent<NativeScrollEvent>) => {
      const len = messagesLenRef.current;
      if (len === 0) {
        updateAtBottom(true);
        return;
      }
      const metrics = measureScrollMetrics(event);
      if (!metrics) return;
      if (metrics.maxOffset <= 0) {
        updateAtBottom(true);
        return;
      }
      const { hideAtBottom, showWhenAway } = getScrollThresholds();
      const { distanceFromBottom } = metrics;
      if (distanceFromBottom <= hideAtBottom) {
        updateAtBottom(true);
      } else if (distanceFromBottom >= showWhenAway) {
        updateAtBottom(false);
      }
    },
    [getScrollThresholds, measureScrollMetrics, updateAtBottom],
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
    viewportHeightRef.current = 0;
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
      setChatLoading(false);
      return;
    }
    const openChatId = typeof routeChatId === "string" ? routeChatId : null;
    const prevOpenChatId = priorRouteChatIdRef.current;
    if (prevOpenChatId && prevOpenChatId !== openChatId) {
      discardEmptyChat(prevOpenChatId);
    }
    if (openChatId && draftChatIdRef.current) {
      clearDraftChat();
    }
    priorRouteChatIdRef.current = openChatId;

    let cancelled = false;
    (async () => {
      // No route chat → a fresh, unsaved chat. The DB row is created lazily on
      // first send (see handleSend), so we never accumulate empty chats.
      if (!openChatId) {
        setChatLoading(false);
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
        setChatLoading(false);
        return;
      }
      setChatLoading(true);
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
        setMessages(page.messages);
        setHasMoreOlder(page.has_more);
        // Backend backfills missing titles on list_messages — poll for it
        if (!chat.title && page.messages.length > 0) {
          pollForTitle(token, openChatId);
        }
      } finally {
        if (!cancelled) setChatLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, routeChatId]);

  // Once a lazily-created chat is ready, flush the queued first message
  useEffect(() => {
    if (chatId && pendingSend) {
      const { text, skipUserBubble, attachmentIds, localImageUri } = pendingSend;
      setPendingSend(null);
      sendMessage(text, { skipUserBubble, attachmentIds, localImageUri });
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

  const showActionBanner = useCallback(
    (message: string, icon?: keyof typeof Ionicons.glyphMap) => {
      setActionBanner({ message, icon });
    },
    [],
  );

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
      showActionBanner(t("common.error"), "cloud-offline-outline");
    } finally {
      setLoadingOlder(false);
    }
  }, [token, chatId, loadingOlder, hasMoreOlder, messages, showActionBanner, t]);

  const handlePlanSelect = (plan: "free" | "pro") => {
    setShowPlanPicker(false);
    if (plan === "pro" && !isPro) {
      setUpgradeVisible(true);
    }
  };

  const planLabel = isPro ? t("chat.plan_pro") : t("chat.plan_free");

  const startNewChat = useCallback(() => {
    if (streaming) return;
    discardEmptyChat(chatId);
    clearDraftChat();
    pendingProjectIdRef.current = null;
    setInput("");
    setChatId(null);
    setChatTitle(null);
    setPinned(false);
    setMessages([]);
    setHasMoreOlder(false);
    if (routeChatId != null) {
      router.setParams({ chatId: undefined });
    }
    void prepareDraftChat();
  }, [
    streaming,
    chatId,
    discardEmptyChat,
    clearDraftChat,
    routeChatId,
    router,
    setMessages,
    prepareDraftChat,
  ]);

  const beginChatLaunch = useCallback(
    (launch: QueuedChatLaunch | string) => {
      const queued =
        typeof launch === "string" ? { prompt: launch.trim() } : launch;
      if (!queued.prompt.trim()) return;
      if (streaming) stopGeneration();
      discardEmptyChat(chatId);
      clearDraftChat();
      draftProjectIdRef.current = queued.projectId ?? null;
      pendingProjectIdRef.current = queued.projectId ?? null;
      setInput("");
      setChatId(null);
      setChatTitle(null);
      setPinned(false);
      setMessages([]);
      setHasMoreOlder(false);
      creatingRef.current = false;
      if (routeChatId != null) {
        router.setParams({ chatId: undefined });
      }
      pendingLaunchRef.current = queued.prompt.trim();
      setPendingLaunch(queued.prompt.trim());
      void prepareDraftChat(queued.projectId);
    },
    [
      streaming,
      stopGeneration,
      discardEmptyChat,
      chatId,
      clearDraftChat,
      routeChatId,
      router,
      setMessages,
      prepareDraftChat,
    ],
  );

  // Project "Ask Recall" / "Quiz with Recall" — queue survives nested navigation.
  useFocusEffect(
    useCallback(() => {
      if (!token) return;
      const queued = takeQueuedChatLaunch();
      if (queued) beginChatLaunch(queued);
    }, [token, beginChatLaunch]),
  );

  // Fallback when prompt is passed via route params (legacy / deep links).
  useEffect(() => {
    if (!token) return;
    const prompt = typeof routePrompt === "string" ? routePrompt.trim() : "";
    const launchId = typeof routeLaunchId === "string" ? routeLaunchId : "";
    if (!prompt || !launchId || handledLaunchIdRef.current === launchId) return;
    handledLaunchIdRef.current = launchId;
    router.setParams({ prompt: undefined, launchId: undefined, chatId: undefined });
    beginChatLaunch(prompt);
  }, [routePrompt, routeLaunchId, token, router, beginChatLaunch]);

  // Let the drawer's "New chat" trigger this same action.
  useEffect(() => {
    registerNewChat(startNewChat);
  }, [startNewChat]);

  const handleSend = async (overrideText?: string) => {
    const text = (overrideText ?? input).trim();
    if ((!text && !pendingAttachment) || streaming || !token || creatingRef.current || attachBusy) return;
    if (editingMessageId && pendingAttachment) {
      Alert.alert(t("chat.error_title"), t("chat.edit_no_attachments"));
      return;
    }
    tap();

    let attachmentIds: string[] | undefined;
    const attached = pendingAttachment;
    if (attached) {
      setAttachBusy(true);
      try {
        const id = await uploadChatAttachment(token, attached);
        attachmentIds = [id];
      } catch (error) {
        Alert.alert(
          t("chat.error_title"),
          error instanceof Error ? error.message : t("common.error"),
        );
        setAttachBusy(false);
        return;
      }
      setAttachBusy(false);
      setPendingAttachment(null);
    }

    setInput("");
    newMessageCountRef.current += 1;

    if (editingMessageId && chatId) {
      const editId = editingMessageId;
      setEditingMessageId(null);
      void editMessage(editId, text);
      return;
    }

    if (!chatId) {
      creatingRef.current = true;
      const optimisticId = `local-${Date.now()}`;
      const sendText = messageTextForSend(text, attached);
      const display =
        text || (attached?.kind === "file" ? attached.fileName : sendText);
      setMessages((prev) => [
        ...prev,
        {
          id: optimisticId,
          role: "user",
          content: display,
          model: null,
          local_image_uri: attached?.kind === "image" ? attached.localUri : null,
          created_at: new Date().toISOString(),
        },
      ]);
      try {
        const id = await prepareDraftChat();
        if (!id) throw new Error("Could not create chat");
        skipLoadForChatIdRef.current = id;
        setChatTitle(null);
        setChatId(id);
        draftChatIdRef.current = null;
        setDraftChatId(null);
        router.setParams({ chatId: id });
        setPendingSend({
          text: sendText,
          skipUserBubble: true,
          attachmentIds,
          localImageUri: attached?.kind === "image" ? attached.localUri : null,
        });
      } catch {
        setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
        setInput(text);
      } finally {
        creatingRef.current = false;
      }
      return;
    }
    newMessageCountRef.current += 1;
    sendMessage(messageTextForSend(text, attached), {
      attachmentIds,
      localImageUri: attached?.kind === "image" ? attached.localUri : null,
    });
  };

  const handlePickAttachment = () => {
    if (!token || attachBusy || streaming) return;
    Keyboard.dismiss();
    setShowPlanPicker(false);
    setAttachSheetOpen(true);
  };

  const waitForPickerUi = useCallback(
    () =>
      new Promise<void>((resolve) => {
        InteractionManager.runAfterInteractions(() => {
          requestAnimationFrame(() => {
            requestAnimationFrame(() => resolve());
          });
        });
      }),
    [],
  );

  const handleAttachmentSheetSelect = useCallback(
    async (source: AttachmentSource) => {
      if (attachPickInFlightRef.current || !token || attachBusy || streaming) return;
      attachPickInFlightRef.current = true;
      setAttachSheetOpen(false);
      await waitForPickerUi();

      if (!token || attachBusy || streaming) {
        attachPickInFlightRef.current = false;
        return;
      }

      try {
        const picked =
          source === "camera"
            ? await pickFromCamera()
            : source === "photo"
              ? await pickFromPhotoLibrary()
              : await pickDocument();
        if (picked) setPendingAttachment(picked);
      } catch (error) {
        Alert.alert(
          t("chat.attach_failed"),
          error instanceof Error ? error.message : t("common.error"),
        );
      } finally {
        attachPickInFlightRef.current = false;
      }
    },
    [attachBusy, streaming, t, token, waitForPickerUi],
  );

  useEffect(() => {
    if (!pendingLaunch || chatId || streaming || creatingRef.current) return;
    const text = pendingLaunchRef.current ?? pendingLaunch;
    pendingLaunchRef.current = null;
    setPendingLaunch(null);
    void handleSend(text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingLaunch, chatId, streaming]);

  const handleQuizAnswer = useCallback(
    (letter: "A" | "B" | "C" | "D") => {
      if (streaming || creatingRef.current) return;
      void handleSend(letter);
    },
    // handleSend is stable enough for quiz taps; avoid stale streaming guard.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [streaming, chatId],
  );

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

  const dismissActionBanner = useCallback(() => setActionBanner(null), []);

  const handleShare = useCallback(async () => {
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
  }, [token, chatId, chatTitle, messages]);

  const handleEditMessage = useCallback((message: Message) => {
    if (streaming) return;
    const parsed = parseUserMessageContent(message.content);
    setInput(parsed.caption || message.content);
    setEditingMessageId(message.id);
    setPendingAttachment(null);
  }, [streaming]);

  const renderItem = useCallback(
    ({ item, index }: { item: Message; index: number }) => {
      const priorUserText =
        item.role === "assistant" && index > 0 && messages[index - 1]?.role === "user"
          ? messages[index - 1].content
          : null;
      return (
        <MessageBubble
          message={item}
          priorUserText={priorUserText}
          isGenerating={streaming && item.id === "streaming"}
          isLastAssistant={
            item.role === "assistant" && item.id === lastAssistantId
          }
          onRegenerate={
            item.role === "assistant" &&
            item.id === lastAssistantId &&
            !streaming
              ? () => regenerateResponse()
              : undefined
          }
          onEdit={handleEditMessage}
          canEdit={item.role === "user" && !streaming && !item.id.startsWith("local-")}
          onFeedback={handleFeedback}
          onQuizAnswer={
            item.role === "assistant" && item.id === lastAssistantId && !streaming
              ? handleQuizAnswer
              : undefined
          }
          quizDisabled={streaming || creatingRef.current}
        />
      );
    },
    [messages, streaming, lastAssistantId, regenerateResponse, handleEditMessage, handleFeedback, handleQuizAnswer],
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
      showActionBanner(t("chat.renamed_toast"), "pencil-outline");
    } catch {
      Alert.alert(t("common.error"), t("chat.rename_failed"));
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
      showActionBanner(
        next ? t("chat.pinned_toast") : t("chat.unpinned_toast"),
        next ? "bookmark" : "bookmark-outline",
      );
    } catch {
      setPinned(!next);
      Alert.alert(t("common.error"), t("chat.pin_failed"));
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
              showActionBanner(t("chat.deleted_toast"), "trash-outline");
              setTimeout(() => {
                router.canGoBack() ? router.back() : router.replace("/");
              }, 700);
            } catch {
              Alert.alert(t("common.error"), t("chat.delete_failed"));
            }
          },
        },
      ],
    );
  };

  if (!token) return <Redirect href="/login" />;

  const headerInset = insets.top + HEADER_BAR_HEIGHT;
  const fadeHeight = headerInset + HEADER_FADE_EXTRA;
  const composerLift =
    keyboardHeight > 0 ? keyboardHeight + KEYBOARD_LIFT_EXTRA : 0;
  const composerBottomPad =
    keyboardHeight > 0 ? 0 : Math.max(insets.bottom, 10);
  const composerBlockHeight = COMPOSER_HEIGHT + composerAttachmentExtra(pendingAttachment);
  const composerClearance = composerBlockHeight + composerBottomPad + composerLift;
  const listBottomPad =
    composerBlockHeight +
    composerBottomPad +
    composerLift +
    (messages.length > 0 && !streaming ? FEEDBACK_ROW_HEIGHT : 0);
  listBottomPadRef.current = listBottomPad;
  const emptyHeight = Math.max(
    160,
    windowHeight - headerInset - composerClearance,
  );
  const menuOverlayOpen = attachSheetOpen || showPlanPicker;

  return (
    <>
      <ChatActionsSheet
        visible={menuVisible}
        title={chatTitle}
        pinned={pinned}
        onClose={closeMenu}
        onShare={() => {
          tap();
          closeMenu();
          void handleShare();
        }}
        onRename={() => {
          tap();
          closeMenu();
          openRename();
        }}
        onTogglePin={() => {
          tap();
          closeMenu();
          void togglePin();
        }}
        onDelete={() => {
          tap();
          closeMenu();
          confirmDelete();
        }}
      />

      <ChatRenameSheet
        visible={renameVisible}
        value={renameText}
        onChangeText={setRenameText}
        onClose={() => setRenameVisible(false)}
        onSave={() => void confirmRename()}
      />

      <View style={s.container}>
        <ActionBanner
          message={actionBanner?.message ?? null}
          icon={actionBanner?.icon}
          bottomOffset={composerClearance + 12}
          onDismiss={dismissActionBanner}
        />
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
              chatLoading && routeChatId ? (
                <View style={[s.empty, { height: emptyHeight }]}>
                  <StateView variant="loading" compact />
                </View>
              ) : (
                <View style={[s.empty, { height: emptyHeight }]}>
                  <HomeStarters onSelect={handleSend} />
                </View>
              )
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
                menuOverlayOpen && s.headerMuted,
              ]}
              pointerEvents={menuOverlayOpen ? "none" : "box-none"}
              collapsable={false}
              renderToHardwareTextureAndroid
            >
              <Pressable
                style={({ pressed }) => [
                  s.headerBtn,
                  menuOverlayOpen && s.headerBtnMuted,
                  pressed && !menuOverlayOpen && s.headerBtnPressed,
                ]}
                onPress={openDrawer}
                hitSlop={12}
              >
                <HamburgerIcon size={22} color={C.text} />
              </Pressable>
              <View style={s.headerSpacer} />
              <View style={s.headerRight}>
                {showIndicator ? (
                  <Pressable
                    style={s.headerBtn}
                    onPress={() => {
                      tap();
                      router.push({ pathname: "/todos", params: { focus: "reminders" } });
                    }}
                    hitSlop={12}
                    accessibilityRole="button"
                    accessibilityLabel={t("reminders.badge_accessibility", {
                      count: unseenCount,
                    })}
                  >
                    <View style={s.headerIconWrap}>
                      <Ionicons name="notifications-outline" size={22} color={C.text} />
                      <ReminderBadge count={unseenCount} style={s.headerBadge} />
                    </View>
                  </Pressable>
                ) : null}
                {messages.length > 0 ? (
                  <Pressable
                    style={s.headerBtn}
                    onPress={startNewChat}
                    hitSlop={12}
                    accessibilityRole="button"
                    accessibilityLabel={t("chat.new_chat")}
                  >
                    <Ionicons name="create-outline" size={22} color={C.text} />
                  </Pressable>
                ) : null}
                {messages.length > 0 && (
                  <Pressable
                    style={s.headerBtn}
                    onPress={() => setMenuVisible((v) => !v)}
                    hitSlop={12}
                    accessibilityRole="button"
                    accessibilityLabel={t("chat.menu")}
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
              accessibilityLabel={t("chat.scroll_to_latest")}
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

        {(showPlanPicker || attachSheetOpen) && !drawerOpen && (
          <Pressable
            style={s.pickerBackdrop}
            onPress={() => {
              setShowPlanPicker(false);
              setAttachSheetOpen(false);
            }}
            accessibilityLabel="Close menu"
          />
        )}

        {!drawerOpen && (
          <View
            style={[
              s.composerBlock,
              { bottom: composerLift, paddingBottom: composerBottomPad },
            ]}
          >
            {showPlanPicker && (
              <View style={s.picker}>
                <Pressable
                  style={[s.pickerItem, !isPro && s.pickerItemActive]}
                  onPress={() => handlePlanSelect("free")}
                >
                  <Text
                    style={[s.pickerLabel, !isPro && s.pickerLabelActive, { flex: 1 }]}
                  >
                    {t("chat.plan_free")}
                  </Text>
                  {!isPro ? <Text style={s.pickerCheck}>✓</Text> : null}
                </Pressable>
                <Pressable
                  style={[s.pickerItem, isPro && s.pickerItemActive]}
                  onPress={() => handlePlanSelect("pro")}
                >
                  <Text
                    style={[s.pickerLabel, isPro && s.pickerLabelActive, { flex: 1 }]}
                  >
                    {t("chat.plan_pro")}
                  </Text>
                  {!isPro ? (
                    <Ionicons name="lock-closed" size={14} color={C.textTertiary} />
                  ) : (
                    <Text style={s.pickerCheck}>✓</Text>
                  )}
                </Pressable>
              </View>
            )}

            <View style={s.composerAnchor}>
              <SuggestedRemindersNudge token={token} />
              {editingMessageId ? (
                <View style={s.editBanner}>
                  <Text style={s.editBannerText}>{t("chat.editing_message")}</Text>
                  <Pressable onPress={() => { setEditingMessageId(null); setInput(""); }}>
                    <Text style={s.editBannerCancel}>{t("common.cancel")}</Text>
                  </Pressable>
                </View>
              ) : null}
              {attachSheetOpen && (
                <View style={s.attachMenuFloat} pointerEvents="box-none">
                  <AttachmentSourceSheet
                    onSelect={(source) => void handleAttachmentSheetSelect(source)}
                  />
                </View>
              )}
              <View style={s.composer}>
              <View style={s.inputWrap}>
                {pendingAttachment ? (
                  <ComposerAttachmentPreview
                    attachment={pendingAttachment}
                    uploading={attachBusy}
                    onRemove={() => setPendingAttachment(null)}
                  />
                ) : null}
                <View style={s.inputRowMain}>
                  <Pressable
                    style={s.attachBtn}
                    onPress={handlePickAttachment}
                    disabled={attachBusy || streaming}
                    hitSlop={6}
                    accessibilityLabel={t("chat.attach_a11y")}
                  >
                    <Ionicons name="attach-outline" size={22} color={C.primary} />
                  </Pressable>
                  <TextInput
                    style={s.input}
                    placeholder={t("chat.placeholder")}
                    placeholderTextColor={C.textTertiary}
                    value={input}
                    onChangeText={setInput}
                    onFocus={() => {
                      setShowPlanPicker(false);
                      setAttachSheetOpen(false);
                    }}
                    multiline
                    returnKeyType="default"
                  />
                  <View style={s.sendBtnSlot}>
                    {streaming ? (
                      <Pressable style={s.sendBtn} onPress={stopGeneration}>
                        <Text style={s.sendIcon}>■</Text>
                      </Pressable>
                    ) : input.trim() || pendingAttachment ? (
                      <Pressable style={s.sendBtn} onPress={() => void handleSend()}>
                        <Text style={s.sendIcon}>↑</Text>
                      </Pressable>
                    ) : null}
                  </View>
                </View>
                <View style={s.composerMetaRow}>
                  <Pressable
                    style={s.planPill}
                    onPress={() => {
                      setAttachSheetOpen(false);
                      setShowPlanPicker((v) => !v);
                    }}
                    hitSlop={6}
                  >
                    <Text style={[s.planPillText, isPro && s.planPillTextPro]}>
                      {planLabel}
                    </Text>
                    <Ionicons
                      name={showPlanPicker ? "chevron-up" : "chevron-down"}
                      size={12}
                      color={C.textTertiary}
                    />
                  </Pressable>
                </View>
              </View>
            </View>
          </View>
          </View>
        )}

        <UpgradeSheet visible={upgradeVisible} onClose={() => setUpgradeVisible(false)} />
      </View>
    </>
  );
}

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
  headerMuted: {
    opacity: 0.55,
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
  headerBtnMuted: {
    backgroundColor: "transparent",
  },
  headerBtnPressed: {
    backgroundColor: C.surfaceAlt,
  },
  headerRight: { flexDirection: "row", alignItems: "center", zIndex: 101 },
  headerIconWrap: {
    width: 24,
    height: 24,
    alignItems: "center",
    justifyContent: "center",
  },
  headerBadge: { position: "absolute", top: -4, right: -8 },

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
    paddingVertical: 16,
  },
  headerSpacer: { flex: 1, pointerEvents: "none" as const },

  pickerBackdrop: {
    ...StyleSheet.absoluteFill,
    zIndex: 105,
    backgroundColor: C.scrim,
  },

  composerBlock: {
    position: "absolute",
    left: 0,
    right: 0,
    zIndex: 110,
    backgroundColor: C.bg,
    paddingHorizontal: 12,
    paddingTop: 2,
  },
  composerAnchor: {
    position: "relative",
  },
  editBanner: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginHorizontal: 4,
    marginBottom: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 12,
    backgroundColor: C.primaryLight,
  },
  editBannerText: { fontSize: 13, fontWeight: "600", color: C.primary },
  editBannerCancel: { fontSize: 13, fontWeight: "600", color: C.textSecondary },
  attachMenuFloat: {
    position: "absolute",
    left: 0,
    right: 14,
    bottom: "100%",
    marginBottom: 6,
    zIndex: 2,
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
  attachBtn: {
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 1,
  },
  input: {
    flex: 1,
    fontSize: 16,
    color: C.text,
    maxHeight: 100,
    paddingVertical: 0,
    minHeight: 22,
  },
  composerMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 6,
    gap: 8,
  },
  planPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingVertical: 2,
    paddingRight: 2,
  },
  planPillText: {
    fontSize: 12,
    fontWeight: "600",
    color: C.textSecondary,
  },
  planPillTextPro: {
    color: "#FF9F0A",
  },
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

export default function HomeScreen() {
  return (
    <DrawerShell>
      <ChatScreen />
    </DrawerShell>
  );
}
