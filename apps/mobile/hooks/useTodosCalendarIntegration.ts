import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Alert } from "react-native";
import { useFocusEffect } from "expo-router";
import { useTranslation } from "react-i18next";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";

import { isReminder } from "@/components/todos/todoHelpers";
import { api, GoogleCalendarEvent, SuggestedReminder, Todo } from "@/lib/api";
import {
  dropSuggestedReminder,
  fetchSuggestedReminders,
  undeleteSuggestedReminder,
} from "@/lib/cache/suggestedRemindersCache";
import {
  buildCalendarOverlapNotes,
  buildReminderOverlapNotes,
} from "@/lib/todos/reminderOverlap";
import { syncTodoReminders } from "@/lib/todos/todoReminders";
import {
  calendarEventsOnDay,
  formatDayHeading,
  localDateKey,
  parseDateKey,
  remindersOnDay,
  startOfMonth,
  suggestedRemindersOnDay,
} from "@/lib/todos/reminderCalendar";

type Params = {
  token: string | null;
  todos: Todo[];
  highlight?: string;
  refresh: (opts?: { silent?: boolean; force?: boolean }) => Promise<void>;
  markSeen: () => Promise<void>;
  setTodos: React.Dispatch<React.SetStateAction<Todo[]>>;
};

export function useTodosCalendarIntegration({
  token,
  todos,
  highlight,
  refresh,
  markSeen,
  setTodos,
}: Params) {
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const reportError = useCallback((bodyKey: string) => {
    if (feedback) feedback.error(t(bodyKey));
    else Alert.alert(t("todos.error"), t(bodyKey));
  }, [feedback, t]);
  const [selectedDay, setSelectedDay] = useState(() => localDateKey(new Date()));
  const [visibleMonth, setVisibleMonth] = useState(() => startOfMonth(new Date()));
  const [calendarEvents, setCalendarEvents] = useState<GoogleCalendarEvent[]>([]);
  const [calendarLoadError, setCalendarLoadError] = useState(false);
  const [suggestedReminders, setSuggestedReminders] = useState<SuggestedReminder[]>([]);
  const [suggestedLoadError, setSuggestedLoadError] = useState(false);
  const [suggestionBusyId, setSuggestionBusyId] = useState<string | null>(null);
  const suggestionBusyRef = useRef<string | null>(null);

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
    if (!accessToken) return;

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
  }, []);

  const loadSuggestedReminders = useCallback(async () => {
    const accessToken = tokenRef.current;
    if (!accessToken) return;
    try {
      const result = await fetchSuggestedReminders(accessToken);
      setSuggestedReminders(result?.reminders ?? []);
      setSuggestedLoadError(false);
    } catch {
      setSuggestedReminders([]);
      setSuggestedLoadError(true);
    }
  }, []);

  const loadCalendarEventsRef = useRef(loadCalendarEvents);
  loadCalendarEventsRef.current = loadCalendarEvents;
  const loadSuggestedRemindersRef = useRef(loadSuggestedReminders);
  loadSuggestedRemindersRef.current = loadSuggestedReminders;

  // Empty deps so a mid-screen token refresh does not re-trigger calendar
  // load and flip the spinner back on.
  useFocusEffect(
    useCallback(() => {
      void refreshRef.current({ silent: true });
      void markSeenRef.current();
      if (tokenRef.current) {
        void loadCalendarEventsRef.current();
        void loadSuggestedRemindersRef.current();
      }
    }, []),
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
      if (!token || suggestionBusyRef.current) return;
      suggestionBusyRef.current = reminder.id;
      setSuggestionBusyId(reminder.id);
      dropSuggestedReminder(reminder.id, setSuggestedReminders);
      try {
        const created = await api.addSuggestedReminder(token, reminder.id);
        setTodos((prev) => [created, ...prev]);
        void syncTodoReminders([created, ...todos]);
        void refresh({ silent: true, force: true });
      } catch {
        undeleteSuggestedReminder(reminder, setSuggestedReminders);
        reportError("todos.error_create");
      } finally {
        suggestionBusyRef.current = null;
        setSuggestionBusyId(null);
      }
    },
    [refresh, reportError, setTodos, todos, token],
  );

  const handleDismissSuggestion = useCallback(
    async (reminder: SuggestedReminder) => {
      if (!token || suggestionBusyRef.current) return;
      suggestionBusyRef.current = reminder.id;
      setSuggestionBusyId(reminder.id);
      dropSuggestedReminder(reminder.id, setSuggestedReminders);
      try {
        await api.dismissSuggestedReminder(token, reminder.id);
      } catch {
        undeleteSuggestedReminder(reminder, setSuggestedReminders);
        reportError("common.error");
      } finally {
        suggestionBusyRef.current = null;
        setSuggestionBusyId(null);
      }
    },
    [reportError, token],
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
    suggestedLoadError,
    suggestionBusyId,
    handleAddSuggestion,
    handleDismissSuggestion,
    loadSuggestedReminders,
    overlapNotes,
    selectedDayReminders,
    selectedDayMeetings,
    selectedDaySuggestions,
    selectedDayHeading,
  };
}
