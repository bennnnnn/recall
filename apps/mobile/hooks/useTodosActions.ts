import { useCallback, useMemo, useRef, useState } from "react";
import { Alert, Platform } from "react-native";
import type { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { useTranslation } from "react-i18next";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";

import { dayKeyForDue, defaultDueDate } from "@/components/todos/todoHelpers";
import { api, type RecurrenceRule, Todo } from "@/lib/api";
import { toDueAtIso } from "@/lib/todos/dueDate";
import { markReminderIdsSeen } from "@/lib/reminderSeen";
import {
  cancelTodoReminder,
  syncTodoReminders,
} from "@/lib/todos/todoReminders";
import {
  buildOptimisticTodo,
  removeTodoById,
  replaceTodoById,
} from "@/lib/todos/optimisticTodo";
import { DEFAULT_TOPIC } from "@/lib/todoTopics";

type Params = {
  token: string | null;
  userId: string | undefined;
  todos: Todo[];
  setTodos: React.Dispatch<React.SetStateAction<Todo[]>>;
  refresh: (opts?: { silent?: boolean; force?: boolean }) => Promise<void>;
  goToDay: (dayKey: string) => void;
};

export function useTodosActions({
  token,
  userId,
  todos,
  setTodos,
  refresh,
  goToDay,
}: Params) {
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const reportError = useCallback((bodyKey: string) => {
    if (feedback) feedback.error(t(bodyKey));
    else Alert.alert(t("todos.error"), t(bodyKey));
  }, [feedback, t]);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [duePicker, setDuePicker] = useState<{ todo: Todo; date: Date } | null>(null);
  const [savingReminder, setSavingReminder] = useState(false);
  const [pendingIds, setPendingIds] = useState<Set<string>>(() => new Set());
  const pendingIdsRef = useRef(new Set<string>());
  const savingReminderRef = useRef(false);

  const setPending = useCallback((id: string, pending: boolean) => {
    const next = new Set(pendingIdsRef.current);
    if (pending) next.add(id);
    else next.delete(id);
    pendingIdsRef.current = next;
    setPendingIds(next);
  }, []);

  const busyTodoIds = useMemo(() => {
    const next = new Set(pendingIds);
    if (togglingId) next.add(togglingId);
    return next;
  }, [pendingIds, togglingId]);

  const handleCreateReminder = useCallback(
    async (
      content: string,
      dueDate: Date,
      onCreated: () => void,
      recurrence: RecurrenceRule | null = null,
    ) => {
      if (!token || savingReminderRef.current) return;
      const trimmed = content.trim();
      if (!trimmed) return;
      savingReminderRef.current = true;
      setSavingReminder(true);
      const dueIso = toDueAtIso(dueDate);
      const optimistic = buildOptimisticTodo({
        content: trimmed,
        topic: DEFAULT_TOPIC,
        dueAt: dueIso,
        recurrenceRule: recurrence,
      });
      goToDay(dayKeyForDue(dueDate, dueIso));
      setPending(optimistic.id, true);
      setTodos((prev) => {
        const next = [optimistic, ...prev];
        void syncTodoReminders(next);
        return next;
      });
      onCreated();
      try {
        const created = await api.createTodo(token, trimmed, DEFAULT_TOPIC, {
          dueAt: dueIso,
          recurrenceRule: recurrence,
        });
        setTodos((prev) => replaceTodoById(prev, optimistic.id, created));
        if (userId) void markReminderIdsSeen(userId, [created.id]);
        void refresh({ silent: true, force: true });
      } catch {
        setTodos((prev) => removeTodoById(prev, optimistic.id));
        reportError("todos.error_create");
      } finally {
        setPending(optimistic.id, false);
        savingReminderRef.current = false;
        setSavingReminder(false);
      }
    },
    [goToDay, refresh, reportError, setPending, setTodos, token, userId],
  );

  const handleToggle = useCallback(
    async (todo: Todo) => {
      if (!token || pendingIdsRef.current.has(todo.id)) return;
      const nextChecked = !todo.checked;
      const original = [...todos];
      setTogglingId(todo.id);
      setPending(todo.id, true);
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
        reportError("todos.error_toggle");
      } finally {
        setPending(todo.id, false);
        setTogglingId(null);
        void refresh({ silent: true, force: true });
      }
    },
    [refresh, reportError, setPending, setTodos, todos, token],
  );

  const handleDeleteItem = useCallback(
    (todo: Todo) => {
      Alert.alert(t("todos.delete_confirm"), `"${todo.content}"`, [
        { text: t("common.cancel"), style: "cancel" },
        {
          text: t("common.delete"),
          style: "destructive",
          onPress: async () => {
            if (!token || pendingIdsRef.current.has(todo.id)) return;
            setPending(todo.id, true);
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
              reportError("todos.error_delete");
            } finally {
              setPending(todo.id, false);
              void refresh({ silent: true, force: true });
            }
          },
        },
      ]);
    },
    [refresh, reportError, setPending, setTodos, t, todos, token],
  );

  const applyDueDate = useCallback(
    async (todo: Todo, date: Date) => {
      if (!token || pendingIdsRef.current.has(todo.id)) return false;
      const dueIso = toDueAtIso(date);
      const original = [...todos];
      const previousDay = todo.due_at
        ? dayKeyForDue(new Date(todo.due_at), todo.due_at)
        : null;
      setPending(todo.id, true);
      goToDay(dayKeyForDue(date, dueIso));
      setTodos((prev) => {
        const next = prev.map((item) =>
          item.id === todo.id ? { ...item, due_at: dueIso } : item,
        );
        void syncTodoReminders(next);
        return next;
      });
      try {
        const updated = await api.updateTodo(token, todo.id, {
          due_at: dueIso,
        });
        goToDay(dayKeyForDue(date, updated.due_at ?? dueIso));
        setTodos((prev) => {
          const next = prev.map((item) => (item.id === todo.id ? updated : item));
          void syncTodoReminders(next);
          return next;
        });
        void refresh({ silent: true, force: true });
        return true;
      } catch {
        setTodos(original);
        if (previousDay) {
          goToDay(previousDay);
        }
        reportError("todos.error_due");
        return false;
      } finally {
        setPending(todo.id, false);
      }
    },
    [goToDay, refresh, reportError, setPending, setTodos, todos, token],
  );

  const openDuePicker = useCallback((todo: Todo) => {
    setDuePicker({
      todo,
      date: todo.due_at ? new Date(todo.due_at) : defaultDueDate(),
    });
  }, []);

  const onDuePickerChange = useCallback(
    (event: DateTimePickerEvent, date?: Date) => {
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
    },
    [duePicker, applyDueDate],
  );

  const confirmDuePicker = useCallback(async () => {
    if (!duePicker) return;
    const { todo, date } = duePicker;
    const saved = await applyDueDate(todo, date);
    if (saved) setDuePicker(null);
  }, [duePicker, applyDueDate]);

  return {
    togglingId,
    busyTodoIds,
    duePicker,
    setDuePicker,
    savingReminder,
    handleCreateReminder,
    handleToggle,
    handleDeleteItem,
    openDuePicker,
    onDuePickerChange,
    confirmDuePicker,
  };
}
