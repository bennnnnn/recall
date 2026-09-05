import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Alert } from "react-native";
import { useFocusEffect } from "expo-router";
import { useTranslation } from "react-i18next";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useSuggestedReminderActions } from "@/hooks/useSuggestedReminderActions";
import { isReminder } from "@/components/todos/todoHelpers";
import { api, type GoogleCalendarEvent, type Todo } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import {
  fetchSuggestedReminders, getCachedSuggestedReminders, subscribeSuggestedRemindersCache,
} from "@/lib/cache/suggestedRemindersCache";
import { buildCalendarOverlapNotes, buildReminderOverlapNotes } from "@/lib/todos/reminderOverlap";
import {
  calendarEventsOnDay, formatDayHeading, localDateKey, parseDateKey, remindersOnDay,
  startOfMonth, suggestedRemindersOnDay,
} from "@/lib/todos/reminderCalendar";

type Params = {
  token: string | null;
  todos: Todo[];
  highlight?: string;
  refresh: (opts?: { silent?: boolean; force?: boolean; afterPending?: boolean }) => Promise<void>;
  markSeen: () => Promise<void>;
  setTodos: React.Dispatch<React.SetStateAction<Todo[]>>;
  pushEnabled?: boolean;
  isCurrentSession?: () => boolean;
  isCurrentView?: () => boolean;
};
const alwaysCurrent = () => true;

export function useTodosCalendarIntegration({ token, todos, highlight, refresh, markSeen,
  setTodos, isCurrentSession = alwaysCurrent, isCurrentView = alwaysCurrent,
}: Params) {
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const session = getSessionGeneration();
  const signedIn = Boolean(token);
  const owner = useMemo(() => ({ session, signedIn,
    initial: {
      selectedDay: localDateKey(new Date()), visibleMonth: startOfMonth(new Date()),
      calendarEvents: [] as GoogleCalendarEvent[], calendarLoadError: false,
      suggestedReminders: signedIn ? getCachedSuggestedReminders()?.reminders ?? [] : [], suggestedLoadError: false,
    },
  }), [session, signedIn]);
  const ownerRef = useRef(owner);
  ownerRef.current = owner;
  const mounted = useRef(true);
  const focus = useRef<object | null>({});
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const isSameOwner = useCallback(() => owner.signedIn && ownerRef.current === owner &&
    getSessionGeneration() === owner.session && isCurrentSession(), [owner, isCurrentSession]);
  const canAct = useCallback(() => mounted.current && focus.current !== null && isSameOwner() && isCurrentView(),
    [isSameOwner, isCurrentView]);
  const [state, setState] = useState({ owner, ...owner.initial });
  const view = state.owner === owner ? state : owner.initial;
  const publish = useCallback((patch: Partial<typeof owner.initial>) => {
    if (!canAct()) return;
    setState((previous) => ({ ...(previous.owner === owner ? previous : owner.initial), owner, ...patch }));
  }, [canAct, owner]);
  const reportError = useCallback((key: string) => {
    if (!canAct()) return;
    if (feedback) feedback.error(t(key));
    else Alert.alert(t("todos.error"), t(key));
  }, [canAct, feedback, t]);
  const tokenRef = useRef(token);
  tokenRef.current = token;
  const refreshRef = useRef(refresh);
  refreshRef.current = refresh;
  const markSeenRef = useRef(markSeen);
  markSeenRef.current = markSeen;
  const calendarLoadGen = useRef(0);
  const suggestedLoadGen = useRef(0);
  const goToDay = useCallback((dayKey: string) => {
    const date = parseDateKey(dayKey);
    if (!Number.isFinite(date.getTime())) return;
    publish({ selectedDay: dayKey, visibleMonth: startOfMonth(date) });
  }, [publish]);
  const setVisibleMonth = useCallback((update: React.SetStateAction<Date>) => {
    if (!canAct()) return;
    setState((previous) => {
      const current = previous.owner === owner ? previous : { owner, ...owner.initial };
      const date = typeof update === "function" ? update(current.visibleMonth) : update;
      return Number.isFinite(date.getTime()) ? { ...current, visibleMonth: date } : current;
    });
  }, [canAct, owner]);
  const highlighted = useRef({ owner, param: highlight, consumed: false });
  useEffect(() => {
    if (highlighted.current.owner !== owner || highlighted.current.param !== highlight) {
      highlighted.current = { owner, param: highlight, consumed: false };
    }
    if (!highlight || highlighted.current.consumed || !canAct()) return;
    const due = todos.find((item) => item.id === highlight)?.due_at;
    if (!due || !Number.isFinite(new Date(due).getTime())) return;
    highlighted.current.consumed = true;
    goToDay(localDateKey(new Date(due)));
  }, [owner, highlight, todos, canAct, goToDay]);

  const loadCalendarEvents = useCallback(async () => {
    const accessToken = tokenRef.current;
    if (!accessToken || !canAct()) return;
    const visit = focus.current;
    const generation = ++calendarLoadGen.current;
    publish({ calendarLoadError: false });
    try {
      const result = await api.listGoogleCalendarEvents(accessToken);
      if (!canAct() || visit !== focus.current || generation !== calendarLoadGen.current) return;
      publish(result.load_error ? { calendarLoadError: true } : { calendarEvents: result.events, calendarLoadError: false });
    } catch {
      if (canAct() && visit === focus.current && generation === calendarLoadGen.current) publish({ calendarLoadError: true });
    }
  }, [canAct, publish]);
  const loadSuggestedReminders = useCallback(async () => {
    const accessToken = tokenRef.current;
    if (!accessToken || !canAct()) return;
    const visit = focus.current;
    const generation = ++suggestedLoadGen.current;
    publish({ suggestedLoadError: false });
    const result = await fetchSuggestedReminders(accessToken, { force: true });
    if (!canAct() || visit !== focus.current || generation !== suggestedLoadGen.current) return;
    publish(result ? { suggestedReminders: getCachedSuggestedReminders()?.reminders ?? result.reminders, suggestedLoadError: false }
      : { suggestedLoadError: true });
  }, [canAct, publish]);
  useEffect(() => subscribeSuggestedRemindersCache(() => {
    publish({ suggestedReminders: getCachedSuggestedReminders()?.reminders ?? [] });
  }), [publish]);
  const loadCalendarRef = useRef(loadCalendarEvents);
  loadCalendarRef.current = loadCalendarEvents;
  const loadSuggestedRef = useRef(loadSuggestedReminders);
  loadSuggestedRef.current = loadSuggestedReminders;
  const canActRef = useRef(canAct);
  canActRef.current = canAct;
  useFocusEffect(useCallback(() => {
    const visit = {};
    focus.current = visit;
    if (ownerRef.current === owner && canActRef.current()) {
      void (async () => {
        await refreshRef.current({ silent: true });
        if (ownerRef.current === owner && canActRef.current() && focus.current === visit) await markSeenRef.current();
      })();
      void loadCalendarRef.current();
      void loadSuggestedRef.current();
    }
    return () => {
      if (focus.current === visit) focus.current = null;
      calendarLoadGen.current++;
      suggestedLoadGen.current++;
    };
  }, [owner]));
  const setSuggestedLoadError = useCallback((error: boolean) => publish({ suggestedLoadError: error }), [publish]);
  const suggestionActions = useSuggestedReminderActions({ token, session, isSameOwner, canAct,
    setTodos, refresh, reportError, setLoadError: setSuggestedLoadError });

  const overlapNotes = useMemo(() => {
    const merged = new Map(buildReminderOverlapNotes(todos));
    for (const [id, title] of buildCalendarOverlapNotes(todos, view.calendarEvents)) {
      merged.set(id, merged.has(id) ? `${merged.get(id)} · ${title}` : title);
    }
    return merged;
  }, [todos, view.calendarEvents]);
  const allReminders = useMemo(() => todos.filter(isReminder), [todos]);
  const selectedDayReminders = useMemo(() => remindersOnDay(allReminders, view.selectedDay), [allReminders, view.selectedDay]);
  const selectedDayMeetings = useMemo(() => calendarEventsOnDay(view.calendarEvents, view.selectedDay), [view.calendarEvents, view.selectedDay]);
  const selectedDaySuggestions = useMemo(() => suggestedRemindersOnDay(view.suggestedReminders, view.selectedDay), [view.suggestedReminders, view.selectedDay]);
  const selectedDayHeading = useMemo(() => {
    const now = new Date();
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    if (view.selectedDay === localDateKey(now)) return t("calendar.today_heading");
    if (view.selectedDay === localDateKey(tomorrow)) return t("calendar.tomorrow_heading");
    return formatDayHeading(view.selectedDay, now);
  }, [view.selectedDay, t]);
  return { selectedDay: view.selectedDay, visibleMonth: view.visibleMonth, setVisibleMonth, goToDay,
    calendarEvents: view.calendarEvents, calendarLoadError: view.calendarLoadError, loadCalendarEvents,
    suggestedReminders: view.suggestedReminders, suggestedLoadError: view.suggestedLoadError, loadSuggestedReminders,
    ...suggestionActions, overlapNotes, selectedDayReminders, selectedDayMeetings, selectedDaySuggestions, selectedDayHeading };
}
