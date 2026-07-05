import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Platform,
  Pressable,
  Text,
  View,
} from "react-native";
import { FlashList } from "@shopify/flash-list";
import { Ionicons } from "@expo/vector-icons";
import { type DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { Redirect, useFocusEffect, useLocalSearchParams, useNavigation } from "expo-router";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useTranslation } from "react-i18next";

import { useTheme } from "@/lib/theme";
import { useAuth } from "@/contexts/AuthContext";
import { useTodos } from "@/contexts/TodosContext";
import { api, GoogleCalendarEvent, SuggestedReminder, Todo } from "@/lib/api";
import { toDueAtIso } from "@/lib/dueDate";
import {
  buildCalendarOverlapNotes,
  buildReminderOverlapNotes,
} from "@/lib/reminderOverlap";
import {
  cancelTodoReminder,
  ensureNotificationPermission,
  syncTodoReminders,
} from "@/lib/todoReminders";
import { DEFAULT_TOPIC, normalizeTopic } from "@/lib/todoTopics";
import { CalendarMeetingRow } from "@/components/CalendarMeetingRow";
import { SuggestedReminderRow } from "@/components/SuggestedReminderRow";
import { ListGroupsView } from "@/components/ListGroupsView";
import { ReminderCalendar } from "@/components/ReminderCalendar";
import { StateView } from "@/components/StateView";
import { AddReminderSheet } from "@/components/todos/AddReminderSheet";
import { DuePickerModal } from "@/components/todos/DuePickerModal";
import { NewListSheet } from "@/components/todos/NewListSheet";
import { TodoRow } from "@/components/todos/TodoRow";
import {
  dayKeyForDue,
  defaultDueDate,
  isReminder,
  sortOpen,
} from "@/components/todos/todoHelpers";
import { makeTodosStyles } from "@/components/todos/todosStyles";
import {
  buildListGroups,
  isDefaultListTopic,
  mergeGroupOrder,
} from "@/lib/listGroups";
import { loadListGroupOrder, saveListGroupOrder } from "@/lib/listGroupOrder";
import { markReminderIdsSeen } from "@/lib/reminderSeen";
import {
  calendarEventsOnDay,
  formatDayHeading,
  localDateKey,
  parseDateKey,
  remindersOnDay,
  startOfMonth,
  suggestedRemindersOnDay,
} from "@/lib/reminderCalendar";

type FocusSection = "list" | "reminders";

export default function TodosScreen() {
  const { token, user } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeTodosStyles(C), [C]);
  const navigation = useNavigation();
  const { focus, topic: focusTopic, highlight } = useLocalSearchParams<{
    focus?: string;
    topic?: string;
    highlight?: string;
  }>();
  const focusSection: FocusSection | null =
    focus === "list" || focus === "reminders" ? focus : null;
  const showReminders = focusSection !== "list";
  const showList = focusSection !== "reminders";
  const {
    todos,
    setTodos,
    loading,
    error,
    refresh,
    markSeen,
  } = useTodos();
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [duePicker, setDuePicker] = useState<{ todo: Todo; date: Date } | null>(null);
  const [reminderSheetOpen, setReminderSheetOpen] = useState(false);
  const [newListOpen, setNewListOpen] = useState(false);
  const [savingReminder, setSavingReminder] = useState(false);
  const [groupOrder, setGroupOrder] = useState<string[]>([]);
  const [selectedDay, setSelectedDay] = useState(() => localDateKey(new Date()));
  const [visibleMonth, setVisibleMonth] = useState(() => startOfMonth(new Date()));
  const [calendarEvents, setCalendarEvents] = useState<GoogleCalendarEvent[]>([]);
  const [calendarLoadError, setCalendarLoadError] = useState(false);
  const [calendarLoading, setCalendarLoading] = useState(false);
  const [suggestedReminders, setSuggestedReminders] = useState<SuggestedReminder[]>([]);
  const [suggestionBusyId, setSuggestionBusyId] = useState<string | null>(null);
  const highlightRef = useRef(highlight);
  highlightRef.current = highlight;

  useEffect(() => {
    const id = highlightRef.current;
    if (!id || todos.length === 0) return;
    const todo = todos.find((item) => item.id === id);
    if (!todo?.due_at) return;
    const dayKey = localDateKey(new Date(todo.due_at));
    setSelectedDay(dayKey);
    setVisibleMonth(startOfMonth(parseDateKey(dayKey)));
  }, [highlight, todos]);
  const syncGroupOrder = useCallback(
    async (items: Todo[]) => {
      if (!user?.id) return;
      const saved = await loadListGroupOrder(user.id);
      const topics = [
        ...new Set(
          items.filter((item) => !item.due_at).map((item) => normalizeTopic(item.topic)),
        ),
      ];
      setGroupOrder(mergeGroupOrder(saved, topics));
    },
    [user?.id],
  );

  const loadCalendarEvents = useCallback(async () => {
    if (!token || focusSection === "list") return;
    setCalendarLoading(true);
    setCalendarLoadError(false);
    try {
      const result = await api.listGoogleCalendarEvents(token);
      setCalendarEvents(result.events);
      setCalendarLoadError(Boolean(result.load_error));
    } catch {
      setCalendarEvents([]);
      setCalendarLoadError(true);
    } finally {
      setCalendarLoading(false);
    }
  }, [focusSection, token]);

  useFocusEffect(
    useCallback(() => {
      void refresh({ silent: todos.length > 0 });
      if (focusSection !== "list") {
        void markSeen();
      }
      if (token && focusSection !== "list") {
        void loadCalendarEvents();
        void api
          .listSuggestedReminders(token)
          .then((result) => setSuggestedReminders(result.reminders))
          .catch(() => setSuggestedReminders([]));
      }
    }, [focusSection, loadCalendarEvents, markSeen, refresh, token, todos.length]),
  );

  useEffect(() => {
    if (todos.length > 0) {
      void syncGroupOrder(todos);
    }
  }, [syncGroupOrder, todos]);

  const openReminders = useMemo(
    () => sortOpen(todos.filter((item) => isReminder(item) && !item.checked)),
    [todos],
  );
  const doneItems = useMemo(
    () =>
      [...todos]
        .filter((item) => item.checked)
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [todos],
  );
  const doneReminders = useMemo(
    () => doneItems.filter((item) => isReminder(item)),
    [doneItems],
  );
  const allListGroups = useMemo(
    () => buildListGroups(todos, groupOrder, t("lists.default_group")),
    [todos, groupOrder, t],
  );
  /** User-created lists only; legacy default bucket if no lists yet. */
  const listGroups = useMemo(() => {
    const named = allListGroups.filter((g) => !g.isDefault);
    if (named.length > 0) return named;
    const fallback = allListGroups.find((g) => g.isDefault);
    if (fallback && fallback.open.length + fallback.done.length > 0) return [fallback];
    return [];
  }, [allListGroups]);
  const visibleDone = useMemo(() => {
    if (focusSection === "list" || focusSection === "reminders") return [];
    return doneReminders;
  }, [doneReminders, focusSection]);
  const hasNamedGroups = groupOrder.some((topic) => !isDefaultListTopic(topic));
  const hasListItems = todos.some((item) => !isReminder(item));
  const isEmpty = useMemo(() => {
    if (focusSection === "list") {
      return listGroups.length === 0;
    }
    if (focusSection === "reminders") {
      return openReminders.length === 0 && doneReminders.length === 0;
    }
    return (
      openReminders.length === 0 && !hasListItems && doneReminders.length === 0 && !hasNamedGroups
    );
  }, [
    doneReminders.length,
    focusSection,
    hasListItems,
    hasNamedGroups,
    openReminders.length,
  ]);
  const overlapNotes = useMemo(() => {
    const todoNotes = buildReminderOverlapNotes(todos);
    const calNotes = buildCalendarOverlapNotes(todos, calendarEvents);
    const merged = new Map(todoNotes);
    for (const [id, title] of calNotes.entries()) {
      merged.set(id, merged.has(id) ? `${merged.get(id)} · ${title}` : title);
    }
    return merged;
  }, [calendarEvents, todos]);
  const isRemindersPage = focusSection === "reminders";
  const allReminders = useMemo(() => todos.filter((item) => isReminder(item)), [todos]);
  const selectedDayReminders = useMemo(
    () => remindersOnDay(allReminders, selectedDay),
    [allReminders, selectedDay],
  );
  const selectedDayMeetings = useMemo(
    () => calendarEventsOnDay(calendarEvents, selectedDay),
    [calendarEvents, selectedDay],
  );
  const selectedDaySuggestions = useMemo(
    () => suggestedRemindersOnDay(suggestedReminders, selectedDay),
    [selectedDay, suggestedReminders],
  );
  const selectedDayHeading = useMemo(() => {
    const now = new Date();
    const todayKey = localDateKey(now);
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    if (selectedDay === todayKey) return t("calendar.today_heading");
    if (selectedDay === localDateKey(tomorrow)) return t("calendar.tomorrow_heading");
    return formatDayHeading(selectedDay, now);
  }, [selectedDay, t]);
  const showRemindersEmptyHero = isEmpty && focusSection !== "reminders";

  useEffect(() => {
    const title =
      focusSection === "list"
        ? ""
        : focusSection === "reminders"
          ? t("todos.section_reminders")
          : t("todos.title");
    navigation.setOptions({ title });
  }, [focusSection, navigation, t]);

  const persistGroupOrder = useCallback(
    async (order: string[]) => {
      setGroupOrder(order);
      if (user?.id) await saveListGroupOrder(user.id, order);
    },
    [user?.id],
  );

  const handleCreateListItem = async (topic: string, content: string) => {
    if (!token || !content.trim()) return;
    try {
      const created = await api.createTodo(token, content.trim(), topic);
      setTodos((prev) => [created, ...prev]);
      const nextOrder = mergeGroupOrder(groupOrder, [topic]);
      void persistGroupOrder(nextOrder);
    } catch {
      Alert.alert(t("todos.error"), t("todos.error_create"));
    }
  };

  const handleCreateList = async (name: string) => {
    const topic = name.trim();
    if (!topic || isDefaultListTopic(topic)) return;
    if (groupOrder.some((entry) => entry.toLowerCase() === topic.toLowerCase())) {
      Alert.alert(t("todos.error"), t("lists.group_exists"));
      return;
    }
    const nextOrder = mergeGroupOrder(groupOrder, [topic]);
    await persistGroupOrder(nextOrder);
    setNewListOpen(false);
  };

  const handleReorderGroups = async (topics: string[]) => {
    await persistGroupOrder(topics);
  };

  const handleReorderItems = async (topic: string, ordered: Todo[]) => {
    if (!token) return;
    const original = [...todos];
    const orderMap = new Map(ordered.map((item, index) => [item.id, index]));
    setTodos((prev) =>
      prev.map((item) =>
        orderMap.has(item.id)
          ? { ...item, sort_order: orderMap.get(item.id)!, topic }
          : item,
      ),
    );
    try {
      const updated = await api.reorderTodos(
        token,
        ordered.map((item, index) => ({ id: item.id, sort_order: index, topic })),
      );
      setTodos((prev) => {
        const byId = new Map(updated.map((item) => [item.id, item]));
        return prev.map((item) => byId.get(item.id) ?? item);
      });
    } catch {
      setTodos(original);
      Alert.alert(t("todos.error"), t("todos.error_create"));
    }
  };

  const handleCreateReminder = async (content: string, dueDate: Date) => {
    if (!token) return;
    setSavingReminder(true);
    try {
      const dueIso = toDueAtIso(dueDate);
      const created = await api.createTodo(token, content.trim(), DEFAULT_TOPIC, {
        dueAt: dueIso,
      });
      const dayKey = dayKeyForDue(dueDate, created.due_at ?? dueIso);
      setSelectedDay(dayKey);
      setVisibleMonth(startOfMonth(parseDateKey(dayKey)));
      setTodos((prev) => {
        const next = [created, ...prev];
        void syncTodoReminders(next);
        return next;
      });
      setReminderSheetOpen(false);
      if (user?.id) void markReminderIdsSeen(user.id, [created.id]);
      void refresh({ silent: true, force: true });
    } catch {
      Alert.alert(t("todos.error"), t("todos.error_create"));
    } finally {
      setSavingReminder(false);
    }
  };

  const handleToggle = async (todo: Todo) => {
    if (!token || togglingId === todo.id) return;
    const nextChecked = !todo.checked;
    const original = [...todos];
    setTogglingId(todo.id);
    setTodos((prev) => {
      const next = prev.map((item) =>
        item.id === todo.id ? { ...item, checked: nextChecked } : item,
      );
      void syncTodoReminders(next);
      return next;
    });
    try {
      const updated = await api.updateTodo(token, todo.id, { checked: nextChecked });
      setTodos((prev) => {
        const next = prev.map((item) => (item.id === todo.id ? updated : item));
        void syncTodoReminders(next);
        return next;
      });
    } catch {
      setTodos(original);
      Alert.alert(t("todos.error"), t("todos.error_toggle"));
    } finally {
      setTogglingId(null);
      void refresh({ silent: true, force: true });
    }
  };

  const handleDeleteItem = (todo: Todo) => {
    Alert.alert(t("todos.delete_confirm"), `"${todo.content}"`, [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("common.delete"),
        style: "destructive",
        onPress: async () => {
          if (!token) return;
          const snapshot = [...todos];
          await cancelTodoReminder(todo.id);
          setTodos((prev) => {
            const next = prev.filter((item) => item.id !== todo.id);
            void syncTodoReminders(next);
            return next;
          });
          try {
            await api.deleteTodo(token, todo.id);
          } catch {
            setTodos(snapshot);
            void syncTodoReminders(snapshot);
            Alert.alert(t("todos.error"), t("todos.error_delete"));
          } finally {
            void refresh({ silent: true, force: true });
          }
        },
      },
    ]);
  };

  const handleDeleteList = (topic: string) => {
    const normalized = normalizeTopic(topic);
    const items = todos.filter(
      (item) => !item.due_at && normalizeTopic(item.topic) === normalized,
    );
    if (items.some((item) => !item.checked)) {
      Alert.alert(t("lists.delete_group_blocked_title"), t("lists.delete_group_blocked_body"));
      return;
    }
    Alert.alert(
      t("lists.delete_group_confirm"),
      t("lists.delete_group_body", { name: topic }),
      [
        { text: t("common.cancel"), style: "cancel" },
        {
          text: t("common.delete"),
          style: "destructive",
          onPress: async () => {
            if (!token) return;
            const snapshot = [...todos];
            for (const item of items) {
              await cancelTodoReminder(item.id);
            }
            setTodos((prev) => {
              const filtered = prev.filter(
                (item) =>
                  item.due_at != null || normalizeTopic(item.topic) !== normalized,
              );
              void syncTodoReminders(filtered);
              return filtered;
            });
            const snapshotOrder = [...groupOrder];
            const nextOrder = groupOrder.filter((entry) => entry !== topic);
            await persistGroupOrder(nextOrder);
            try {
              await Promise.all(items.map((item) => api.deleteTodo(token, item.id)));
            } catch {
              setTodos(snapshot);
              void syncTodoReminders(snapshot);
              await persistGroupOrder(snapshotOrder);
              Alert.alert(t("todos.error"), t("todos.error_delete"));
            } finally {
              void refresh({ silent: true, force: true });
            }
          },
        },
      ],
    );
  };

  const applyDueDate = async (todo: Todo, date: Date) => {
    if (!token) return;
    try {
      const dueIso = toDueAtIso(date);
      const updated = await api.updateTodo(token, todo.id, {
        due_at: dueIso,
      });
      if (isRemindersPage) {
        const dayKey = dayKeyForDue(date, updated.due_at ?? dueIso);
        setSelectedDay(dayKey);
        setVisibleMonth(startOfMonth(parseDateKey(dayKey)));
      }
      setTodos((prev) => {
        const next = prev.map((item) => (item.id === todo.id ? updated : item));
        void syncTodoReminders(next);
        return next;
      });
      void refresh({ silent: true, force: true });
    } catch {
      Alert.alert(t("todos.error"), t("todos.error_due"));
    }
  };

  const openDuePicker = (todo: Todo) => {
    void ensureNotificationPermission();
    const date =
      todo.due_at && !Number.isNaN(new Date(todo.due_at).getTime())
        ? new Date(todo.due_at)
        : defaultDueDate();
    setDuePicker({ todo, date });
  };

  const onDuePickerChange = (event: DateTimePickerEvent, date?: Date) => {
    if (Platform.OS === "android") {
      const current = duePicker;
      setDuePicker(null);
      if (event.type === "dismissed" || !date || !current) return;
      void applyDueDate(current.todo, date);
      return;
    }
    if (date) {
      setDuePicker((prev) => (prev ? { ...prev, date } : prev));
    }
  };

  const confirmDuePicker = async () => {
    if (!duePicker) return;
    const { todo, date } = duePicker;
    setDuePicker(null);
    await applyDueDate(todo, date);
  };

  const handleAddSuggestion = async (reminder: SuggestedReminder) => {
    if (!token || suggestionBusyId) return;
    setSuggestionBusyId(reminder.id);
    try {
      const created = await api.addSuggestedReminder(token, reminder.id);
      setSuggestedReminders((prev) => prev.filter((item) => item.id !== reminder.id));
      setTodos((prev) => [created, ...prev]);
      void syncTodoReminders([created, ...todos]);
      void refresh({ silent: true, force: true });
    } catch {
      Alert.alert(t("todos.error"), t("todos.error_create"));
    } finally {
      setSuggestionBusyId(null);
    }
  };

  const handleDismissSuggestion = async (reminder: SuggestedReminder) => {
    if (!token || suggestionBusyId) return;
    setSuggestionBusyId(reminder.id);
    try {
      await api.dismissSuggestedReminder(token, reminder.id);
      setSuggestedReminders((prev) => prev.filter((item) => item.id !== reminder.id));
    } catch {
      Alert.alert(t("todos.error"), t("common.error"));
    } finally {
      setSuggestionBusyId(null);
    }
  };

  // The screen is a multi-mode dashboard. The genuinely long, flat lists are
  // `openReminders` (non-calendar mode) and `visibleDone` — those go into the
  // FlashList data so rows are recycled. The calendar day-view, ListGroupsView,
  // and the new-group link are bounded/structured, so they render in the header.
  // (These hooks must run before the early returns below — rules-of-hooks.)
  type TodoListItem =
    | { type: "remindersHeader"; key: string; title: string }
    | { type: "doneHeader"; key: string; title: string }
    | { type: "todoRow"; key: string; todo: Todo; done: boolean };

  const todosData = useMemo<TodoListItem[]>(() => {
    const items: TodoListItem[] = [];
    if (showReminders && !isRemindersPage && openReminders.length > 0) {
      if (!focusSection) {
        items.push({
          type: "remindersHeader",
          key: "reminders-h",
          title: t("todos.section_reminders"),
        });
      }
      for (const todo of openReminders) {
        items.push({ type: "todoRow", key: todo.id, todo, done: false });
      }
    }
    if (visibleDone.length > 0) {
      items.push({
        type: "doneHeader",
        key: "done-h",
        title: `${t("todos.done")} (${visibleDone.length})`,
      });
      for (const todo of visibleDone) {
        items.push({ type: "todoRow", key: todo.id, todo, done: true });
      }
    }
    return items;
  }, [showReminders, isRemindersPage, openReminders, focusSection, visibleDone, t]);

  const renderTodoItem = useCallback(
    ({ item }: { item: TodoListItem }) => {
      if (item.type === "remindersHeader" || item.type === "doneHeader") {
        return <Text style={s.sectionHeading}>{item.title}</Text>;
      }
      const todo = item.todo;
      if (item.done) {
        return (
          <TodoRow
            key={todo.id}
            todo={todo}
            busy={togglingId === todo.id}
            onToggle={() => void handleToggle(todo)}
            onDue={isReminder(todo) ? () => openDuePicker(todo) : undefined}
            onDelete={() => handleDeleteItem(todo)}
          />
        );
      }
      return (
        <TodoRow
          key={todo.id}
          todo={todo}
          highlighted={highlight === todo.id}
          overlapWith={overlapNotes.get(todo.id)}
          busy={togglingId === todo.id}
          onToggle={() => void handleToggle(todo)}
          onDue={() => openDuePicker(todo)}
          onDelete={() => handleDeleteItem(todo)}
        />
      );
    },
    [s, togglingId, highlight, overlapNotes, handleToggle, openDuePicker, handleDeleteItem],
  );

  if (!token) return <Redirect href="/login" />;

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color={C.primary} />
      </View>
    );
  }

  // The screen is a multi-mode dashboard. The genuinely long, flat lists are
  // `openReminders` (non-calendar mode) and `visibleDone` — those go into the
  // FlashList data so rows are recycled. The calendar day-view, ListGroupsView,
  // and the new-group link are bounded/structured, so they render in the header.
  const todosHeader = (
    <>
      {error ? (
        <View style={s.empty}>
          <Ionicons
            name="cloud-offline-outline"
            size={48}
            color={C.textTertiary}
            style={s.emptyIcon}
          />
          <Text style={s.emptyTitle}>{t("common.error")}</Text>
          <Pressable
            style={s.retryBtn}
            onPress={() => {
              void refresh();
            }}
          >
            <Text style={s.retryText}>{t("common.retry")}</Text>
          </Pressable>
        </View>
      ) : showRemindersEmptyHero ? (
        <View style={s.empty}>
          <Ionicons
            name={focusSection === "list" ? "list-outline" : "checkbox-outline"}
            size={48}
            color={C.primary}
            style={s.emptyIcon}
          />
          <Text style={s.emptyTitle}>{t("todos.empty_title")}</Text>
          <Text style={s.emptyBody}>
            {focusSection === "list"
              ? t("todos.empty_list_body")
              : t("todos.empty_body")}
          </Text>
        </View>
      ) : null}

      {showReminders && isRemindersPage ? (
        <View style={s.section}>
          <ReminderCalendar
            reminders={openReminders}
            calendarEvents={calendarEvents}
            suggestedReminders={suggestedReminders}
            selectedDay={selectedDay}
            visibleMonth={visibleMonth}
            onSelectDay={(dayKey) => {
              setSelectedDay(dayKey);
              setVisibleMonth(startOfMonth(parseDateKey(dayKey)));
            }}
            onVisibleMonthChange={setVisibleMonth}
          />
          {calendarLoading ? (
            <View style={s.calendarLoading}>
              <ActivityIndicator size="small" color={C.primary} />
            </View>
          ) : null}
          {calendarLoadError ? (
            <StateView
              variant="error"
              compact
              message={t("calendar.load_failed")}
              onRetry={() => void loadCalendarEvents()}
              retryLabel={t("common.retry")}
            />
          ) : null}
          {selectedDaySuggestions.length > 0 ? (
            <>
              <Text style={s.sectionHeading}>{t("calendar.from_email")}</Text>
              {selectedDaySuggestions.map((reminder) => (
                <SuggestedReminderRow
                  key={reminder.id}
                  reminder={reminder}
                  busy={suggestionBusyId === reminder.id}
                  onAdd={() => void handleAddSuggestion(reminder)}
                  onDismiss={() => void handleDismissSuggestion(reminder)}
                />
              ))}
            </>
          ) : null}
          <Text style={s.dayHeading}>{selectedDayHeading}</Text>
          {selectedDayMeetings.length === 0 &&
          selectedDayReminders.length === 0 &&
          selectedDaySuggestions.length === 0 ? (
            <Text style={s.sectionEmpty}>{t("calendar.no_items_day")}</Text>
          ) : (
            <>
              {selectedDayMeetings.map((event) => (
                <CalendarMeetingRow key={event.id} event={event} />
              ))}
              {selectedDayReminders.map((todo) => (
                <TodoRow
                  key={todo.id}
                  todo={todo}
                  highlighted={highlight === todo.id}
                  overlapWith={overlapNotes.get(todo.id)}
                  busy={togglingId === todo.id}
                  onToggle={() => void handleToggle(todo)}
                  onDue={() => openDuePicker(todo)}
                  onDelete={() => handleDeleteItem(todo)}
                />
              ))}
            </>
          )}
        </View>
      ) : null}

      {showReminders && !isRemindersPage && openReminders.length === 0 && !showRemindersEmptyHero ? (
        <Text style={s.sectionEmpty}>{t("todos.reminders_empty")}</Text>
      ) : null}

      {showList ? (
        <>
          <Pressable style={s.newListLink} onPress={() => setNewListOpen(true)}>
            <Ionicons name="add-circle-outline" size={20} color={C.primary} />
            <Text style={s.newListLinkText}>{t("lists.new_group")}</Text>
          </Pressable>
          <ListGroupsView
            groups={listGroups}
            initialExpandedTopic={focusTopic ?? undefined}
            togglingId={togglingId}
            onReorderGroups={(topics) => void handleReorderGroups(topics)}
            onReorderItems={(topic, ordered) => void handleReorderItems(topic, ordered)}
            onToggle={(todo) => void handleToggle(todo)}
            onAddItem={(topic, text) => void handleCreateListItem(topic, text)}
            onDeleteItem={handleDeleteItem}
            onDeleteList={handleDeleteList}
          />
        </>
      ) : null}
    </>
  );

  return (
    <GestureHandlerRootView style={s.root}>
      {showReminders ? (
      <View style={s.topBar}>
          <Pressable
            style={[s.topBtn, s.topBtnSolo]}
            onPress={() => {
              void ensureNotificationPermission();
              setReminderSheetOpen(true);
            }}
          >
            <Ionicons name="notifications-outline" size={20} color={C.primary} />
            <Text style={s.topBtnText}>{t("todos.add_reminder")}</Text>
          </Pressable>
      </View>
      ) : null}

      <FlashList
        style={s.list}
        data={todosData}
        renderItem={renderTodoItem}
        keyExtractor={(item) => item.key}
        getItemType={(item) => item.type}
        contentContainerStyle={showRemindersEmptyHero && !error ? s.listEmpty : undefined}
        keyboardShouldPersistTaps="handled"
        ListHeaderComponent={todosHeader}
      />

      <NewListSheet
        visible={newListOpen}
        onClose={() => setNewListOpen(false)}
        onSave={(name) => void handleCreateList(name)}
      />

      <AddReminderSheet
        visible={reminderSheetOpen}
        saving={savingReminder}
        todos={todos}
        onClose={() => setReminderSheetOpen(false)}
        onSave={(content, dueDate) => void handleCreateReminder(content, dueDate)}
      />

      <DuePickerModal
        todos={todos}
        duePicker={duePicker}
        onDismiss={() => setDuePicker(null)}
        onChange={onDuePickerChange}
        onConfirm={() => void confirmDuePicker()}
      />
    </GestureHandlerRootView>
  );
}
