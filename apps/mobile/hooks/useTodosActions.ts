import { useCallback, useMemo, useRef, useState } from "react";
import { Alert, Platform } from "react-native";
import type { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { useTranslation } from "react-i18next";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";

import { dayKeyForDue, defaultDueDate } from "@/components/todos/todoHelpers";
import { api, Todo } from "@/lib/api";
import { toDueAtIso } from "@/lib/todos/dueDate";
import { isDefaultListTopic, mergeGroupOrder } from "@/lib/listGroups";
import { markReminderIdsSeen } from "@/lib/reminderSeen";
import {
  cancelTodoReminder,
  ensureNotificationPermission,
  syncTodoReminders,
} from "@/lib/todos/todoReminders";
import { DEFAULT_TOPIC, normalizeTopic } from "@/lib/todoTopics";

type Params = {
  token: string | null;
  userId: string | undefined;
  todos: Todo[];
  setTodos: React.Dispatch<React.SetStateAction<Todo[]>>;
  refresh: (opts?: { silent?: boolean; force?: boolean }) => Promise<void>;
  groupOrder: string[];
  persistGroupOrder: (order: string[]) => Promise<void>;
  goToDay: (dayKey: string) => void;
  isRemindersPage: boolean;
};

export function useTodosActions({
  token,
  userId,
  todos,
  setTodos,
  refresh,
  groupOrder,
  persistGroupOrder,
  goToDay,
  isRemindersPage,
}: Params) {
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [duePicker, setDuePicker] = useState<{ todo: Todo; date: Date } | null>(null);
  const [savingReminder, setSavingReminder] = useState(false);
  const [creatingList, setCreatingList] = useState(false);
  const [pendingIds, setPendingIds] = useState<Set<string>>(() => new Set());
  const pendingIdsRef = useRef(new Set<string>());
  const creatingListRef = useRef(false);
  const creatingItemRef = useRef(false);
  const savingReminderRef = useRef(false);
  const reorderRef = useRef(false);

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

  const handleCreateListItem = useCallback(
    async (topic: string, content: string) => {
      if (!token || !content.trim() || creatingItemRef.current) return;
      creatingItemRef.current = true;
      const trimmed = content.trim();
      const normalizedTopic = normalizeTopic(topic);
      const openInTopic = todos.filter(
        (item) =>
          !item.due_at &&
          !item.checked &&
          normalizeTopic(item.topic) === normalizedTopic,
      );
      const nextSort =
        openInTopic.reduce(
          (max, item) => Math.max(max, item.sort_order ?? Number.MAX_SAFE_INTEGER),
          -1,
        ) + 1;
      const optimisticId = `local-todo-${Date.now()}`;
      const now = new Date().toISOString();
      const optimistic: Todo = {
        id: optimisticId,
        content: trimmed,
        topic: normalizedTopic,
        checked: false,
        due_at: null,
        sort_order: nextSort,
        chat_id: null,
        project_id: null,
        created_at: now,
        updated_at: now,
      };
      setPending(optimisticId, true);
      setTodos((prev) => [...prev, optimistic]);
      void persistGroupOrder(mergeGroupOrder(groupOrder, [normalizedTopic]));
      try {
        const created = await api.createTodo(token, trimmed, topic);
        setTodos((prev) =>
          prev.map((item) => (item.id === optimisticId ? created : item)),
        );
      } catch {
        setTodos((prev) => prev.filter((item) => item.id !== optimisticId));
        if (feedback) feedback.error(t("todos.error_create"));
        else Alert.alert(t("todos.error"), t("todos.error_create"));
      } finally {
        creatingItemRef.current = false;
        setPending(optimisticId, false);
      }
    },
    [feedback, groupOrder, persistGroupOrder, setPending, setTodos, t, todos, token],
  );

  const handleCreateList = useCallback(
    async (name: string, onCreated: () => void) => {
      if (creatingListRef.current) return;
      const topic = name.trim();
      if (!topic || isDefaultListTopic(topic)) return;
      if (groupOrder.some((entry) => entry.toLowerCase() === topic.toLowerCase())) {
        Alert.alert(t("todos.error"), t("lists.group_exists"));
        return;
      }
      const nextOrder = [...groupOrder, topic];
      creatingListRef.current = true;
      setCreatingList(true);
      try {
        await persistGroupOrder(nextOrder);
        onCreated();
      } catch {
        if (feedback) feedback.error(t("todos.error_create"));
        else Alert.alert(t("todos.error"), t("todos.error_create"));
      } finally {
        creatingListRef.current = false;
        setCreatingList(false);
      }
    },
    [feedback, groupOrder, persistGroupOrder, t],
  );

  const handleReorderGroups = useCallback(
    async (topics: string[]) => {
      if (reorderRef.current) return;
      reorderRef.current = true;
      try {
        await persistGroupOrder(topics);
      } catch {
        if (feedback) feedback.error(t("todos.error_toggle"));
        else Alert.alert(t("todos.error"), t("todos.error_toggle"));
      } finally {
        reorderRef.current = false;
      }
    },
    [feedback, persistGroupOrder, t],
  );

  const handleReorderItems = useCallback(
    async (topic: string, ordered: Todo[]) => {
      if (!token || reorderRef.current) return;
      reorderRef.current = true;
      const orderedIds = new Set(ordered.map((item) => item.id));
      const withPending = new Set(pendingIdsRef.current);
      orderedIds.forEach((id) => withPending.add(id));
      pendingIdsRef.current = withPending;
      setPendingIds(withPending);
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
        if (feedback) feedback.error(t("todos.error_toggle"));
        else Alert.alert(t("todos.error"), t("todos.error_toggle"));
      } finally {
        const withoutPending = new Set(pendingIdsRef.current);
        orderedIds.forEach((id) => withoutPending.delete(id));
        pendingIdsRef.current = withoutPending;
        setPendingIds(withoutPending);
        reorderRef.current = false;
      }
    },
    [feedback, setTodos, t, todos, token],
  );

  const handleCreateReminder = useCallback(
    async (content: string, dueDate: Date, onCreated: () => void) => {
      if (!token || savingReminderRef.current) return;
      savingReminderRef.current = true;
      setSavingReminder(true);
      try {
        const dueIso = toDueAtIso(dueDate);
        const created = await api.createTodo(token, content.trim(), DEFAULT_TOPIC, {
          dueAt: dueIso,
        });
        goToDay(dayKeyForDue(dueDate, created.due_at ?? dueIso));
        setTodos((prev) => {
          const next = [created, ...prev];
          void syncTodoReminders(next);
          return next;
        });
        onCreated();
        if (userId) void markReminderIdsSeen(userId, [created.id]);
        void refresh({ silent: true, force: true });
      } catch {
        if (feedback) feedback.error(t("todos.error_create"));
        else Alert.alert(t("todos.error"), t("todos.error_create"));
      } finally {
        savingReminderRef.current = false;
        setSavingReminder(false);
      }
    },
    [feedback, goToDay, refresh, setTodos, t, token, userId],
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
        if (feedback) feedback.error(t("todos.error_toggle"));
        else Alert.alert(t("todos.error"), t("todos.error_toggle"));
      } finally {
        setPending(todo.id, false);
        setTogglingId(null);
        void refresh({ silent: true, force: true });
      }
    },
    [feedback, refresh, setPending, setTodos, t, todos, token],
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
              if (feedback) feedback.error(t("todos.error_delete"));
              else Alert.alert(t("todos.error"), t("todos.error_delete"));
            } finally {
              setPending(todo.id, false);
              void refresh({ silent: true, force: true });
            }
          },
        },
      ]);
    },
    [feedback, refresh, setPending, setTodos, t, todos, token],
  );

  const handleDeleteList = useCallback(
    (topic: string) => {
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
              if (items.some((item) => pendingIdsRef.current.has(item.id))) return;
              if (items.length > 0 && !token) return;
              const snapshot = [...todos];
              items.forEach((item) => setPending(item.id, true));
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
              try {
                await persistGroupOrder(nextOrder);
                // Empty list-first names are device order only — no server
                // rows, and DELETE /todos/topic 404s when nothing is removed.
                if (items.length > 0 && token) {
                  await api.deleteTodoTopic(token, topic);
                }
              } catch {
                setTodos(snapshot);
                void syncTodoReminders(snapshot);
                await persistGroupOrder(snapshotOrder).catch(() => {});
                if (feedback) feedback.error(t("todos.error_delete"));
                else Alert.alert(t("todos.error"), t("todos.error_delete"));
              } finally {
                items.forEach((item) => setPending(item.id, false));
                void refresh({ silent: true, force: true });
              }
            },
          },
        ],
      );
    },
    [feedback, groupOrder, persistGroupOrder, refresh, setPending, setTodos, t, todos, token],
  );

  const applyDueDate = useCallback(
    async (todo: Todo, date: Date) => {
      if (!token || pendingIdsRef.current.has(todo.id)) return false;
      setPending(todo.id, true);
      try {
        const dueIso = toDueAtIso(date);
        const updated = await api.updateTodo(token, todo.id, {
          due_at: dueIso,
        });
        if (isRemindersPage) {
          goToDay(dayKeyForDue(date, updated.due_at ?? dueIso));
        }
        setTodos((prev) => {
          const next = prev.map((item) => (item.id === todo.id ? updated : item));
          void syncTodoReminders(next);
          return next;
        });
        void refresh({ silent: true, force: true });
        return true;
      } catch {
        if (feedback) feedback.error(t("todos.error_due"));
        else Alert.alert(t("todos.error"), t("todos.error_due"));
        return false;
      } finally {
        setPending(todo.id, false);
      }
    },
    [feedback, goToDay, isRemindersPage, refresh, setPending, setTodos, t, token],
  );

  const openDuePicker = useCallback((todo: Todo) => {
    void ensureNotificationPermission();
    const date =
      todo.due_at && !Number.isNaN(new Date(todo.due_at).getTime())
        ? new Date(todo.due_at)
        : defaultDueDate();
    setDuePicker({ todo, date });
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
    creatingList,
    handleCreateListItem,
    handleCreateList,
    handleReorderGroups,
    handleReorderItems,
    handleCreateReminder,
    handleToggle,
    handleDeleteItem,
    handleDeleteList,
    openDuePicker,
    onDuePickerChange,
    confirmDuePicker,
  };
}
