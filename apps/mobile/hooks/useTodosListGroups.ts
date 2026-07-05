import { useCallback, useEffect, useMemo, useState } from "react";

import { buildListGroups, isDefaultListTopic, mergeGroupOrder } from "@/lib/listGroups";
import { loadListGroupOrder, saveListGroupOrder } from "@/lib/listGroupOrder";
import { normalizeTopic } from "@/lib/todoTopics";
import type { Todo } from "@/lib/api";

export function useTodosListGroups(
  userId: string | undefined,
  todos: Todo[],
  defaultGroupLabel: string,
) {
  const [groupOrder, setGroupOrder] = useState<string[]>([]);

  const syncGroupOrder = useCallback(
    async (items: Todo[]) => {
      if (!userId) return;
      const saved = await loadListGroupOrder(userId);
      const topics = [
        ...new Set(
          items.filter((item) => !item.due_at).map((item) => normalizeTopic(item.topic)),
        ),
      ];
      setGroupOrder(mergeGroupOrder(saved, topics));
    },
    [userId],
  );

  useEffect(() => {
    if (todos.length > 0) {
      void syncGroupOrder(todos);
    }
  }, [syncGroupOrder, todos]);

  const persistGroupOrder = useCallback(
    async (order: string[]) => {
      setGroupOrder(order);
      if (userId) await saveListGroupOrder(userId, order);
    },
    [userId],
  );

  const allListGroups = useMemo(
    () => buildListGroups(todos, groupOrder, defaultGroupLabel),
    [todos, groupOrder, defaultGroupLabel],
  );

  const listGroups = useMemo(() => {
    const named = allListGroups.filter((g) => !g.isDefault);
    if (named.length > 0) return named;
    const fallback = allListGroups.find((g) => g.isDefault);
    if (fallback && fallback.open.length + fallback.done.length > 0) return [fallback];
    return [];
  }, [allListGroups]);

  const hasNamedGroups = groupOrder.some((topic) => !isDefaultListTopic(topic));

  return {
    groupOrder,
    persistGroupOrder,
    listGroups,
    hasNamedGroups,
  };
}
