import { useCallback, useEffect, useRef } from "react";
import { useFocusEffect } from "expo-router";

import type { Todo } from "@/lib/api";

type Options = {
  refresh: (opts?: { silent?: boolean; force?: boolean }) => Promise<void>;
  todos: readonly Todo[];
  /** The list came from the server this session. */
  loaded: boolean;
  /** The to-do a link or a reminder push opened the page for. */
  highlightId: string | null;
};

/**
 * To-do reads its list again each time it comes into view once the list is past its stale
 * window (`isContextFresh`, 20 s; within it, nothing is read): a to-do added or ticked on
 * another device showed only after a pull or a return from the background. A link to a to-do
 * the list does not hold (a reminder push for one made on another device) reads the list at
 * once, so its page opens; it is read once per to-do.
 */
export function useTodosFocusRefresh({ refresh, todos, loaded, highlightId }: Options): void {
  useFocusEffect(useCallback(() => {
    void refresh({ silent: true });
  }, [refresh]));
  const readFor = useRef<string | null>(null);
  useEffect(() => {
    if (!highlightId || !loaded || readFor.current === highlightId) return;
    if (todos.some((todo) => todo.id === highlightId)) return;
    readFor.current = highlightId;
    void refresh({ silent: true, force: true });
  }, [highlightId, loaded, todos, refresh]);
}
