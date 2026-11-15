import { useCallback, useState } from "react";

import type { Todo } from "@/lib/api";

/**
 * The To-do list's one fold and its scroll target. The list is one list of sections with
 * Completed folded at the end until its heading is tapped; a to-do the page should show (a
 * new one, or one Home or a push opened) is scrolled to once its row is drawn, Completed
 * opened first when it is done. It replaced switching views: Today hid a to-do added for
 * another day, and the list changed view to show it.
 */
export function useTodoReveal() {
  const [completedOpen, setCompletedOpen] = useState(false);
  const [revealId, setRevealId] = useState<string | null>(null);
  const toggleCompleted = useCallback(() => setCompletedOpen((open) => !open), []);
  const reveal = useCallback((todo: Pick<Todo, "id" | "checked">) => {
    if (todo.checked) setCompletedOpen(true);
    setRevealId(todo.id);
  }, []);
  const revealed = useCallback(() => setRevealId(null), []);
  return { completedOpen, toggleCompleted, revealId, reveal, revealed };
}
