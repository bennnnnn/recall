import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Alert } from "react-native";
import { useFocusEffect } from "expo-router";
import { useTranslation } from "react-i18next";

import { isReminder } from "@/components/todos/todoHelpers";
import { api, GoogleCalendarEvent, SuggestedReminder, Todo } from "@/lib/api";
import {
  buildCalendarOverlapNotes,
  buildReminderOverlapNotes,
} from "@/lib/reminderOverlap";
import { syncTodoReminders } from "@/lib/todoReminders";
import {
  calendarEventsOnDay,
  formatDayHeading,
  localDateKey,
  parseDateKey,
  remindersOnDay,
  startOfMonth,
  suggestedRemindersOnDay,
} from "@/lib/reminderCalendar";

type FocusSection = "list" | "reminders" | null;

type Params = {
  token: string | null;
  focusSection: FocusSection;
  todos: Todo[];
  highlight?: string;
  refresh: (opts?: { silent?: boolean; force?: boolean }) => Promise<void>;
  markSeen: () => Promise<void>;
  setTodos: React.Dispatch<React.SetStateAction<Todo[]>>;
};

export function useTodosCalendarIntegration({
  token,
  focusSection,
  todos,
  highlight,
  refresh,
  markSeen,
  setTodos,
}: Params) {
  const { t } = useTranslation();
  const [selectedDay, setSelectedDay] = useState(() => localDateKey(new Date()));
  const [visibleMonth, setVisibleMonth] = useState(() => startOfMonth(new Date()));
  const [calendarEvents, setCalendarEvents] = useState<GoogleCalendarEvent[]>([]);
  const [calendarLoadError, setCalendarLoadError] = useState(false);
  const [suggestedReminders, setSuggestedReminders] = useState<SuggestedReminder[]>([]);
  const [suggestionBusyId, setSuggestionBusyId] = useState<string | null>(null);

  const highlightRef = useRef(highlight);
  highlightRef.current = highlight;

  const tokenRef = useRef(token);
  tokenRef.current = token;
  const refreshRef = useRef(refresh);
  refreshRef.current = refresh;
  const markSeenRef = useRef(markSeen);
  markSeenRef.current = markSeen;

  const calendarLoadGen = useRef(0);

  const goToDay = useCallback((dayKey: string) => {
    setSelectedDay(dayKey);
    setVisibleMonth(startOfMonth(parseDateKey(dayKey)));
  }, []);

  useEffect(() => {
    const id = highlightRef.current;
    if (!id || todos.length === 0) return;
    const todo = todos.find((item) => item.id === id);
    if (!todo?.due_at) return;
    goToDay(localDateKey(new Date(todo.due_at)));
  }, [highlight, todos, goToDay]);

  const loadCalendarEvents = useCallback(async () => {
    const accessToken = tokenRef.current;
    if (!accessToken || focusSection === "list") return;

    const gen = ++calendarLoadGen.current;
    setCalendarLoadError(false);
    try {
      const result = await api.listGoogleCalendarEvents(accessToken);
      if (gen !== calendarLoadGen.current) return;
      setCalendarEvents(result.events);
      setCalendarLoadError(Boolean(result.load_error));
    } catch {
      if (gen !== calendarLoadGen.current) return;
      setCalendarEvents([]);
      setCalendarLoadError(true);
    }
  }, [focusSection]);

  const loadSuggestedReminders = useCallback(async () => {
    const accessToken = tokenRef.current;
    if (!accessToken || focusSection === "list") return;
    try {
      const result = await api.listSuggestedReminders(accessToken);
      setSuggestedReminders(result.reminders);
    } catch {
      setSuggestedReminders([]);
    }
  }, [focusSection]);

  const loadCalendarEventsRef = useRef(loadCalendarEvents);
  loadCalendarEventsRef.current = loadCalendarEvents;
  const loadSuggestedRemindersRef = useRef(loadSuggestedReminders);
  loadSuggestedRemindersRef.current = loadSuggestedReminders;

  // Depend only on focusSection so a mid-screen token refresh does not
  // re-trigger calendar load and flip the spinner back on.
  useFocusEffect(
    useCallback(() => {
      void refreshRef.current({ silent: true });
      if (focusSection === "list") return;
      void markSeenRef.current();
      if (tokenRef.current) {
        void loadCalendarEventsRef.current();
        void loadSuggestedRemindersRef.current();
      }
    }, [focusSection]),
  );

  const overlapNotes = useMemo(() => {
    const todoNotes = buildReminderOverlapNotes(todos);
    const calNotes = buildCalendarOverlapNotes(todos, calendarEvents);
    const merged = new Map(todoNotes);
    for (const [id, title] of calNotes.entries()) {
      merged.set(id, merged.has(id) ? `${merged.get(id)} · ${title}` : title);
    }
    return merged;
  }, [calendarEvents, todos]);

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

  const handleAddSuggestion = useCallback(
    async (reminder: SuggestedReminder) => {
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
    },
    [token, suggestionBusyId, setTodos, todos, refresh, t],
  );

  const handleDismissSuggestion = useCallback(
    async (reminder: SuggestedReminder) => {
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
    },
    [token, suggestionBusyId, t],
  );

  return {
    selectedDay,
    visibleMonth,
    setVisibleMonth,
    goToDay,
    calendarEvents,
    calendarLoadError,
    loadCalendarEvents,
    suggestedReminders,
    suggestionBusyId,
    handleAddSuggestion,
    handleDismissSuggestion,
    overlapNotes,
    selectedDayReminders,
    selectedDayMeetings,
    selectedDaySuggestions,
    selectedDayHeading,
  };
}
