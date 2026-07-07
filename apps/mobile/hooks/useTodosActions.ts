import { useCallback, useState } from "react";
import { Alert, Platform } from "react-native";
import type { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { useTranslation } from "react-i18next";

import { dayKeyForDue, defaultDueDate } from "@/components/todos/todoHelpers";
import { api, Todo } from "@/lib/api";
import { toDueAtIso } from "@/lib/dueDate";
import { isDefaultListTopic, mergeGroupOrder } from "@/lib/listGroups";
import { markReminderIdsSeen } from "@/lib/reminderSeen";
import {
  cancelTodoReminder,
  ensureNotificationPermission,
  syncTodoReminders,
} from "@/lib/todoReminders";
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
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [duePicker, setDuePicker] = useState<{ todo: Todo; date: Date } | null>(null);
  const [savingReminder, setSavingReminder] = useState(false);

  const handleCreateListItem = useCallback(
    async (topic: string, content: string) => {
      if (!token || !content.trim()) return;
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
        created_at: now,
        updated_at: now,
      };
      setTodos((prev) => [...prev, optimistic]);
      void persistGroupOrder(mergeGroupOrder(groupOrder, [topic]));
      try {
        const created = await api.createTodo(token, trimmed, topic);
        setTodos((prev) =>
          prev.map((item) => (item.id === optimisticId ? created : item)),
        );
      } catch {
        setTodos((prev) => prev.filter((item) => item.id !== optimisticId));
        Alert.alert(t("todos.error"), t("todos.error_create"));
      }
    },
    [token, todos, setTodos, groupOrder, persistGroupOrder, t],
  );

  const handleCreateList = useCallback(
    async (name: string, onCreated: () => void) => {
      const topic = name.trim();
      if (!topic || isDefaultListTopic(topic)) return;
      if (groupOrder.some((entry) => entry.toLowerCase() === topic.toLowerCase())) {
        Alert.alert(t("todos.error"), t("lists.group_exists"));
        return;
      }
      const nextOrder = mergeGroupOrder(groupOrder, [topic]);
      await persistGroupOrder(nextOrder);
      onCreated();
    },
    [groupOrder, persistGroupOrder, t],
  );

  const handleReorderGroups = useCallback(
    async (topics: string[]) => {
      await persistGroupOrder(topics);
    },
    [persistGroupOrder],
  );

  const handleReorderItems = useCallback(
    async (topic: string, ordered: Todo[]) => {
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
    },
    [token, todos, setTodos, t],
  );

  const handleCreateReminder = useCallback(
    async (content: string, dueDate: Date, onCreated: () => void) => {
      if (!token) return;
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
        Alert.alert(t("todos.error"), t("todos.error_create"));
      } finally {
        setSavingReminder(false);
      }
    },
    [token, goToDay, setTodos, userId, refresh, t],
  );

  const handleToggle = useCallback(
    async (todo: Todo) => {
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
    },
    [token, togglingId, todos, setTodos, refresh, t],
  );

  const handleDeleteItem = useCallback(
    (todo: Todo) => {
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
    },
    [token, todos, setTodos, refresh, t],
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
                // One batched DELETE instead of N per-item requests. The
                // server's delete_by_topic removes only items without a due_at
                // (lists, not reminders), which matches the items filtered
                // above. Local reminder cancels above are per-item (no batch
                // API for expo-notifications) but stay local/non-network.
                await api.deleteTodoTopic(token, topic);
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
    },
    [token, todos, setTodos, groupOrder, persistGroupOrder, refresh, t],
  );

  const applyDueDate = useCallback(
    async (todo: Todo, date: Date) => {
      if (!token) return;
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
      } catch {
        Alert.alert(t("todos.error"), t("todos.error_due"));
      }
    },
    [token, isRemindersPage, goToDay, setTodos, refresh, t],
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
    setDuePicker(null);
    await applyDueDate(todo, date);
  }, [duePicker, applyDueDate]);

  return {
    togglingId,
    duePicker,
    setDuePicker,
    savingReminder,
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
