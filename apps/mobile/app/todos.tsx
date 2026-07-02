import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { FlashList } from "@shopify/flash-list";
import { Ionicons } from "@expo/vector-icons";
import DateTimePicker, {
  type DateTimePickerEvent,
} from "@react-native-community/datetimepicker";
import { Redirect, useFocusEffect, useLocalSearchParams, useNavigation } from "expo-router";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";
import { useAuth } from "@/contexts/AuthContext";
import { useTodos } from "@/contexts/TodosContext";
import { api, GoogleCalendarEvent, SuggestedReminder, Todo } from "@/lib/api";
import { describeDueAt, toDueAtIso } from "@/lib/dueDate";
import {
  buildCalendarOverlapNotes,
  buildReminderOverlapNotes,
  findOverlappingReminder,
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

function sortOpen(items: Todo[]): Todo[] {
  return [...items].sort((a, b) => {
    if (a.checked !== b.checked) return Number(a.checked) - Number(b.checked);
    const aDue = a.due_at ? new Date(a.due_at).getTime() : Number.POSITIVE_INFINITY;
    const bDue = b.due_at ? new Date(b.due_at).getTime() : Number.POSITIVE_INFINITY;
    if (aDue !== bDue) return aDue - bDue;
    return b.created_at.localeCompare(a.created_at);
  });
}

function defaultDueDate(): Date {
  const now = new Date();
  const nineToday = new Date(now);
  nineToday.setHours(9, 0, 0, 0);
  if (nineToday.getTime() > now.getTime()) return nineToday;
  const nextHour = new Date(now);
  nextHour.setMinutes(0, 0, 0);
  nextHour.setHours(nextHour.getHours() + 1);
  return nextHour;
}

function dayKeyForDue(dueDate: Date, dueIso?: string | null): string {
  if (dueIso && !Number.isNaN(new Date(dueIso).getTime())) {
    return localDateKey(new Date(dueIso));
  }
  return localDateKey(dueDate);
}

function isReminder(todo: Todo): boolean {
  return Boolean(todo.due_at);
}

type FocusSection = "list" | "reminders";

export default function TodosScreen() {
  const { token, user } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
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
  const [todoSheetOpen, setTodoSheetOpen] = useState(false);
  const [savingReminder, setSavingReminder] = useState(false);
  const [savingTodo, setSavingTodo] = useState(false);
  const [groupOrder, setGroupOrder] = useState<string[]>([]);
  const [newGroupOpen, setNewGroupOpen] = useState(false);
  const [addListTopic, setAddListTopic] = useState<string | null>(null);
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
  const listGroups = useMemo(
    () => buildListGroups(todos, groupOrder, t("lists.default_group")),
    [todos, groupOrder, t],
  );
  const visibleDone = useMemo(() => {
    if (focusSection === "list" || focusSection === "reminders") return [];
    return doneReminders;
  }, [doneReminders, focusSection]);
  const hasNamedGroups = groupOrder.some((topic) => !isDefaultListTopic(topic));
  const hasListItems = todos.some((item) => !isReminder(item));
  const isEmpty = useMemo(() => {
    if (focusSection === "list") {
      return !hasListItems && !hasNamedGroups;
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
        ? t("todos.section_todos")
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

  const handleCreateTodo = async (content: string, topic = DEFAULT_TOPIC) => {
    if (!token || !content.trim()) return;
    setSavingTodo(true);
    try {
      const created = await api.createTodo(token, content.trim(), topic);
      setTodos((prev) => [created, ...prev]);
      const nextOrder = mergeGroupOrder(groupOrder, [topic]);
      void persistGroupOrder(nextOrder);
      setTodoSheetOpen(false);
      setAddListTopic(null);
    } catch {
      Alert.alert(t("todos.error"), t("todos.error_create"));
    } finally {
      setSavingTodo(false);
    }
  };

  const handleCreateGroup = async (name: string) => {
    const topic = name.trim();
    if (!topic || isDefaultListTopic(topic)) return;
    if (groupOrder.some((entry) => entry.toLowerCase() === topic.toLowerCase())) {
      Alert.alert(t("todos.error"), t("lists.group_exists"));
      return;
    }
    const nextOrder = mergeGroupOrder(groupOrder, [topic]);
    await persistGroupOrder(nextOrder);
    setNewGroupOpen(false);
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

  const handleDeleteGroup = (topic: string, title: string) => {
    if (isDefaultListTopic(topic)) return;
    Alert.alert(t("lists.delete_group_confirm"), t("lists.delete_group_body", { name: title }), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("common.delete"),
        style: "destructive",
        onPress: async () => {
          if (!token) return;
          const toDelete = todos.filter(
            (item) => !item.due_at && normalizeTopic(item.topic) === topic,
          );
          setTodos((prev) => prev.filter((item) => !toDelete.some((d) => d.id === item.id)));
          const nextOrder = groupOrder.filter((entry) => entry !== topic);
          await persistGroupOrder(nextOrder);
          try {
            await Promise.all(toDelete.map((item) => api.deleteTodo(token, item.id)));
          } catch {
            void refresh({ silent: true });
          }
        },
      },
    ]);
  };

  const openAddToList = () => {
    if (listGroups.length <= 1) {
      setAddListTopic(listGroups[0]?.topic ?? DEFAULT_TOPIC);
    } else {
      setAddListTopic(null);
    }
    setTodoSheetOpen(true);
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
      void refresh({ silent: true });
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
      void refresh({ silent: true });
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
          await cancelTodoReminder(todo.id);
          setTodos((prev) => {
            const next = prev.filter((item) => item.id !== todo.id);
            void syncTodoReminders(next);
            return next;
          });
          try {
            await api.deleteTodo(token, todo.id);
          } catch {
            void refresh({ silent: true });
          }
          void refresh({ silent: true });
        },
      },
    ]);
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
      void refresh({ silent: true });
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
      void refresh({ silent: true });
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
          <Pressable style={s.newGroupLink} onPress={() => setNewGroupOpen(true)}>
            <Ionicons name="add-circle-outline" size={18} color={C.primary} />
            <Text style={s.newGroupLinkText}>{t("lists.new_group")}</Text>
          </Pressable>
          <ListGroupsView
            groups={listGroups}
            initialExpandedTopic={focusTopic ?? undefined}
            togglingId={togglingId}
            onReorderGroups={(topics) => void handleReorderGroups(topics)}
            onReorderItems={(topic, ordered) => void handleReorderItems(topic, ordered)}
            onToggle={(todo) => void handleToggle(todo)}
            onDelete={(todo) => handleDeleteItem(todo)}
            onAddItem={(topic, text) => void handleCreateListItem(topic, text)}
            onDeleteGroup={handleDeleteGroup}
          />
        </>
      ) : null}
    </>
  );

  return (
    <GestureHandlerRootView style={s.root}>
      <View style={s.topBar}>
        {showReminders ? (
          <Pressable
            style={[s.topBtn, !showList && s.topBtnSolo]}
            onPress={() => {
              void ensureNotificationPermission();
              setReminderSheetOpen(true);
            }}
          >
            <Ionicons name="notifications-outline" size={20} color={C.primary} />
            <Text style={s.topBtnText}>{t("todos.add_reminder")}</Text>
          </Pressable>
        ) : null}
        {showList ? (
          <Pressable
            style={[s.topBtn, !showReminders && s.topBtnSolo]}
            onPress={openAddToList}
          >
            <Ionicons name="list-outline" size={20} color={C.primary} />
            <Text style={s.topBtnText}>{t("todos.add_todo")}</Text>
          </Pressable>
        ) : null}
      </View>

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

      <AddTodoSheet
        visible={todoSheetOpen}
        saving={savingTodo}
        groups={listGroups}
        selectedTopic={addListTopic}
        onClose={() => {
          setTodoSheetOpen(false);
          setAddListTopic(null);
        }}
        onSave={(content, topic) => void handleCreateTodo(content, topic)}
      />

      <NewGroupSheet
        visible={newGroupOpen}
        onClose={() => setNewGroupOpen(false)}
        onSave={(name) => void handleCreateGroup(name)}
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

function AddTodoSheet({
  visible,
  saving,
  groups,
  selectedTopic,
  onClose,
  onSave,
}: {
  visible: boolean;
  saving: boolean;
  groups: { topic: string; title: string }[];
  selectedTopic: string | null;
  onClose: () => void;
  onSave: (content: string, topic: string) => void;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const [text, setText] = useState("");
  const [topic, setTopic] = useState(DEFAULT_TOPIC);

  useEffect(() => {
    if (!visible) {
      setText("");
      setTopic(DEFAULT_TOPIC);
      return;
    }
    if (selectedTopic) setTopic(selectedTopic);
    else if (groups.length === 1) setTopic(groups[0].topic);
  }, [visible, selectedTopic, groups]);

  const canSave = text.trim().length > 0 && !saving;
  const showGroupPicker = groups.length > 1 && !selectedTopic;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={s.sheetOverlay}>
        <Pressable style={s.sheetBackdrop} onPress={onClose} />
        <View style={s.sheet}>
        <View style={s.sheetHeader}>
          <Pressable onPress={onClose} hitSlop={8}>
            <Text style={s.sheetCancel}>{t("common.cancel")}</Text>
          </Pressable>
          <Text style={s.sheetTitle}>{t("todos.todo_sheet_title")}</Text>
          <Pressable
            onPress={() => canSave && onSave(text, topic)}
            hitSlop={8}
            disabled={!canSave}
          >
            <Text style={[s.sheetSave, !canSave && s.sheetSaveDisabled]}>
              {t("todos.save")}
            </Text>
          </Pressable>
        </View>

        <View style={s.sheetBody}>
          {showGroupPicker ? (
            <>
              <Text style={s.formLabel}>{t("lists.add_to_group")}</Text>
              <View style={s.groupOptions}>
                {groups.map((group) => (
                  <Pressable
                    key={group.topic}
                    style={[s.groupOption, topic === group.topic && s.groupOptionSelected]}
                    onPress={() => setTopic(group.topic)}
                  >
                    <Ionicons
                      name={topic === group.topic ? "radio-button-on" : "radio-button-off"}
                      size={18}
                      color={topic === group.topic ? C.primary : C.textTertiary}
                    />
                    <Text style={s.groupOptionText}>{group.title}</Text>
                  </Pressable>
                ))}
              </View>
            </>
          ) : null}

          <Text style={[s.formLabel, showGroupPicker && s.fieldGap]}>{t("todos.todo_label")}</Text>
          <TextInput
            style={s.titleInput}
            placeholder={t("todos.todo_placeholder")}
            placeholderTextColor={C.textTertiary}
            value={text}
            onChangeText={setText}
            autoFocus
            returnKeyType="done"
            onSubmitEditing={() => canSave && onSave(text, topic)}
            maxLength={500}
          />
        </View>
        </View>
      </View>
    </Modal>
  );
}

function NewGroupSheet({
  visible,
  onClose,
  onSave,
}: {
  visible: boolean;
  onClose: () => void;
  onSave: (name: string) => void;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const [name, setName] = useState("");

  useEffect(() => {
    if (!visible) setName("");
  }, [visible]);

  const canSave = name.trim().length > 0;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={s.sheetOverlay}>
        <Pressable style={s.sheetBackdrop} onPress={onClose} />
        <View style={s.sheet}>
        <View style={s.sheetHeader}>
          <Pressable onPress={onClose} hitSlop={8}>
            <Text style={s.sheetCancel}>{t("common.cancel")}</Text>
          </Pressable>
          <Text style={s.sheetTitle}>{t("lists.new_group_title")}</Text>
          <Pressable
            onPress={() => canSave && onSave(name.trim())}
            hitSlop={8}
            disabled={!canSave}
          >
            <Text style={[s.sheetSave, !canSave && s.sheetSaveDisabled]}>
              {t("todos.save")}
            </Text>
          </Pressable>
        </View>
        <View style={s.sheetBody}>
          <Text style={s.formLabel}>{t("lists.group_name_label")}</Text>
          <TextInput
            style={s.titleInput}
            placeholder={t("lists.group_name_placeholder")}
            placeholderTextColor={C.textTertiary}
            value={name}
            onChangeText={setName}
            autoFocus
            returnKeyType="done"
            maxLength={200}
          />
        </View>
        </View>
      </View>
    </Modal>
  );
}

function AddReminderSheet({
  visible,
  saving,
  todos,
  onClose,
  onSave,
}: {
  visible: boolean;
  saving: boolean;
  todos: Todo[];
  onClose: () => void;
  onSave: (content: string, dueDate: Date) => void;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const [text, setText] = useState("");
  const [dueDate, setDueDate] = useState(() => defaultDueDate());
  const [showPicker, setShowPicker] = useState(Platform.OS === "ios");

  const overlap = useMemo(
    () => findOverlappingReminder(todos, dueDate),
    [todos, dueDate],
  );

  const reset = () => {
    setText("");
    setDueDate(defaultDueDate());
    setShowPicker(Platform.OS === "ios");
  };

  useEffect(() => {
    if (!visible) reset();
  }, [visible]);

  const canSave = text.trim().length > 0 && !saving;

  const handleClose = () => {
    onClose();
  };

  const onPickerChange = (event: DateTimePickerEvent, date?: Date) => {
    if (Platform.OS === "android") {
      setShowPicker(false);
      if (event.type === "dismissed" || !date) return;
      setDueDate(date);
      return;
    }
    if (date) setDueDate(date);
  };

  const handleSave = () => {
    if (!canSave) return;
    onSave(text, dueDate);
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={handleClose}>
      <View style={s.sheetOverlay}>
        <Pressable style={s.sheetBackdrop} onPress={handleClose} />
        <View style={s.sheet}>
        <View style={s.sheetHeader}>
          <Pressable onPress={handleClose} hitSlop={8}>
            <Text style={s.sheetCancel}>{t("common.cancel")}</Text>
          </Pressable>
          <Text style={s.sheetTitle}>{t("todos.reminder_sheet_title")}</Text>
          <Pressable onPress={handleSave} hitSlop={8} disabled={!canSave}>
            <Text style={[s.sheetSave, !canSave && s.sheetSaveDisabled]}>
              {t("todos.save")}
            </Text>
          </Pressable>
        </View>

        <View style={s.sheetBody}>
          <Text style={s.formLabel}>{t("todos.reminder_label")}</Text>
          <TextInput
            style={s.titleInput}
            placeholder={t("todos.reminder_placeholder")}
            placeholderTextColor={C.textTertiary}
            value={text}
            onChangeText={setText}
            autoFocus
            returnKeyType="done"
            maxLength={500}
          />

          <Text style={[s.formLabel, s.fieldGap]}>{t("todos.due_date_required")}</Text>
          {Platform.OS === "ios" && showPicker ? (
            <DateTimePicker
              value={dueDate}
              mode="datetime"
              display="spinner"
              onChange={onPickerChange}
            />
          ) : (
            <Pressable
              style={s.dateChip}
              onPress={() => {
                if (Platform.OS === "android") setShowPicker(true);
                else setShowPicker(true);
              }}
            >
              <Ionicons name="calendar" size={18} color={C.primary} />
              <Text style={s.dateChipText}>
                {describeDueAt(toDueAtIso(dueDate))?.label ?? ""}
              </Text>
            </Pressable>
          )}
          {Platform.OS === "android" && showPicker ? (
            <DateTimePicker
              value={dueDate}
              mode="datetime"
              onChange={onPickerChange}
            />
          ) : null}

          {overlap ? (
            <View style={s.overlapNote}>
              <Ionicons name="information-circle-outline" size={16} color={C.danger} />
              <Text style={s.overlapNoteText}>
                {t("todos.overlap_inline", { task: overlap.content })}
              </Text>
            </View>
          ) : null}
        </View>
        </View>
      </View>
    </Modal>
  );
}

function DuePickerModal({
  todos,
  duePicker,
  onDismiss,
  onChange,
  onConfirm,
}: {
  todos: Todo[];
  duePicker: { todo: Todo; date: Date } | null;
  onDismiss: () => void;
  onChange: (event: DateTimePickerEvent, date?: Date) => void;
  onConfirm: () => void;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  if (!duePicker) return null;

  const overlap = findOverlappingReminder(todos, duePicker.date, {
    excludeId: duePicker.todo.id,
  });

  if (Platform.OS === "android") {
    return (
      <DateTimePicker
        value={duePicker.date}
        mode="datetime"
        onChange={onChange}
      />
    );
  }

  return (
    <Modal transparent animationType="slide" visible>
      <Pressable style={s.pickerBackdrop} onPress={onDismiss} />
      <View style={s.pickerSheet}>
        <View style={s.pickerHeader}>
          <Pressable onPress={onDismiss} hitSlop={8}>
            <Text style={s.pickerCancel}>{t("common.cancel")}</Text>
          </Pressable>
          <Text style={s.pickerTitle}>
            {duePicker.todo.due_at ? t("todos.change_due") : t("todos.set_due")}
          </Text>
          <Pressable onPress={onConfirm} hitSlop={8}>
            <Text style={s.pickerDone}>{t("todos.due_done")}</Text>
          </Pressable>
        </View>
        <DateTimePicker
          value={duePicker.date}
          mode="datetime"
          display="spinner"
          onChange={onChange}
        />
        {overlap ? (
          <View style={[s.overlapNote, s.pickerOverlapNote]}>
            <Ionicons name="information-circle-outline" size={16} color={C.danger} />
            <Text style={s.overlapNoteText}>
              {t("todos.overlap_inline", { task: overlap.content })}
            </Text>
          </View>
        ) : null}
      </View>
    </Modal>
  );
}

function TodoRow({
  todo,
  busy,
  highlighted,
  onToggle,
  onDue,
  onDelete,
  overlapWith,
}: {
  todo: Todo;
  busy?: boolean;
  highlighted?: boolean;
  onToggle: () => void;
  onDue?: () => void;
  onDelete: () => void;
  overlapWith?: string;
}) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const due = describeDueAt(todo.due_at);
  const dueToneStyle =
    due?.tone === "overdue"
      ? s.dueOverdue
      : due?.tone === "today"
        ? s.dueToday
        : s.dueSoon;

  return (
    <View style={[s.todoRow, highlighted && s.todoRowHighlighted]}>
      <Pressable
        onPress={onToggle}
        hitSlop={10}
        style={s.checkbox}
        disabled={busy}
        accessibilityRole="checkbox"
        accessibilityState={{ checked: todo.checked, disabled: busy }}
      >
        <Ionicons
          name={todo.checked ? "checkbox" : "square-outline"}
          size={22}
          color={todo.checked ? C.primary : C.textTertiary}
        />
      </Pressable>
      <View style={s.todoMain}>
        <Text
          style={[s.todoText, todo.checked && s.todoDone]}
          selectable
          numberOfLines={4}
        >
          {todo.content}
        </Text>
        {due && !todo.checked ? (
          <Text style={[s.dueLabel, dueToneStyle]}>{due.label}</Text>
        ) : null}
        {overlapWith && !todo.checked ? (
          <Text style={s.overlapLabel}>
            {t("todos.overlap_inline", { task: overlapWith })}
          </Text>
        ) : null}
      </View>
      {!todo.checked && onDue ? (
        <Pressable onPress={onDue} hitSlop={8} style={s.dueBtn}>
          <Ionicons
            name={todo.due_at ? "calendar" : "calendar-outline"}
            size={18}
            color={todo.due_at ? C.primary : C.textTertiary}
          />
        </Pressable>
      ) : null}
      <Pressable onPress={onDelete} hitSlop={8}>
        <Ionicons name="trash-outline" size={16} color={C.textTertiary} />
      </Pressable>
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: C.bg,
  },
  topBar: {
    flexDirection: "row",
    gap: 10,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
  },
  topBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    backgroundColor: C.primaryLight,
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: 8,
  },
  topBtnText: { fontSize: 15, fontWeight: "700", color: C.primary },
  dayHeading: {
    fontSize: 16,
    fontWeight: "700",
    color: C.text,
    marginTop: 4,
    marginBottom: 8,
  },
  topBtnSolo: { flex: 1 },
  newGroupLink: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  newGroupLinkText: { fontSize: 15, fontWeight: "600", color: C.primary },
  list: { flex: 1 },
  listEmpty: { flexGrow: 1 },
  section: {
    paddingTop: 8,
    paddingBottom: 4,
  },
  calendarLoading: {
    alignItems: "center",
    paddingVertical: 8,
  },
  sectionHeading: {
    fontSize: 12,
    fontWeight: "700",
    color: C.textTertiary,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 4,
  },
  sectionEmpty: {
    fontSize: 14,
    color: C.textTertiary,
    paddingHorizontal: 16,
    paddingBottom: 12,
  },
  todoRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
  },
  todoRowHighlighted: {
    backgroundColor: C.primaryLight,
  },
  checkbox: { padding: 2 },
  todoMain: { flex: 1, gap: 4 },
  todoText: { fontSize: 16, lineHeight: 22, color: C.text },
  dueLabel: { fontSize: 12, fontWeight: "600" },
  dueOverdue: { color: C.danger },
  dueToday: { color: C.primary },
  dueSoon: { color: C.textSecondary },
  overlapLabel: { fontSize: 12, fontWeight: "500", color: C.danger },
  overlapNote: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 6,
    marginTop: 12,
    padding: 10,
    borderRadius: 10,
    backgroundColor: C.dangerLight,
  },
  overlapNoteText: { flex: 1, fontSize: 13, lineHeight: 18, color: C.danger },
  pickerOverlapNote: { marginHorizontal: 16, marginBottom: 8 },
  dueBtn: { padding: 2 },
  todoDone: {
    color: C.textTertiary,
    textDecorationLine: "line-through",
  },
  formLabel: { fontSize: 14, fontWeight: "600", color: C.textSecondary },
  fieldGap: { marginTop: 16 },
  titleInput: {
    fontSize: 17,
    fontWeight: "600",
    color: C.text,
    backgroundColor: C.surface,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: C.border,
  },
  dateChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: C.primaryLight,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    alignSelf: "flex-start",
  },
  dateChipText: { fontSize: 15, fontWeight: "600", color: C.text },
  sheetOverlay: {
    flex: 1,
    justifyContent: "flex-end",
  },
  sheetBackdrop: {
    ...StyleSheet.absoluteFill,
    backgroundColor: C.scrim,
  },
  sheet: {
    backgroundColor: C.surface,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
  },
  sheetHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
  },
  sheetTitle: { fontSize: 17, fontWeight: "700", color: C.text },
  sheetCancel: { fontSize: 16, color: C.textSecondary },
  sheetSave: { fontSize: 16, fontWeight: "700", color: C.primary },
  sheetSaveDisabled: { opacity: 0.4 },
  sheetBody: { padding: 16, paddingBottom: 32, gap: 8 },
  groupOptions: { gap: 4 },
  groupOption: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 8,
    paddingHorizontal: 4,
  },
  groupOptionSelected: { backgroundColor: C.primaryLight, borderRadius: 8 },
  groupOptionText: { fontSize: 15, color: C.text },
  pickerBackdrop: {
    flex: 1,
    backgroundColor: C.scrim,
  },
  pickerSheet: {
    backgroundColor: C.bg,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    paddingBottom: 24,
  },
  pickerHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
  },
  pickerTitle: { fontSize: 16, fontWeight: "700", color: C.text },
  pickerCancel: { fontSize: 16, color: C.textSecondary },
  pickerDone: { fontSize: 16, fontWeight: "700", color: C.primary },
  empty: {
    alignItems: "center",
    paddingTop: 48,
    paddingHorizontal: 32,
    paddingBottom: 16,
  },
  emptyIcon: { opacity: 0.5, marginBottom: 16 },
  emptyTitle: {
    fontSize: 17,
    fontWeight: "700",
    color: C.text,
    marginBottom: 6,
  },
  emptyBody: {
    fontSize: 14,
    color: C.textSecondary,
    textAlign: "center",
    lineHeight: 20,
  },
  retryBtn: {
    marginTop: 16,
    paddingHorizontal: 20,
    paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: C.primary,
  },
  retryText: { fontSize: 14, fontWeight: "600", color: C.onPrimary },
  });
}
