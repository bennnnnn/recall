/**
 * Home overdue / due-soon cards are a one-shot nudge, not a persistent inbox.
 *
 * - Due soon: show while the due time is approaching, until dismissed.
 * - Overdue: show once. After that (or after dismiss), never again.
 * - Dismiss (X): never show that reminder on home again, including after restart.
 *
 * Badge "seen" (reminderSeen) is separate — opening Lists must not resurrect
 * or hide these cards by itself.
 */
import {
  deletePrefFile,
  prefFilePath,
  readPrefFile,
  safePrefUserId,
  writePrefFile,
} from "@/lib/filePrefs";
import type { HomeUrgentTodo } from "@/lib/api";

export type HomeNudgeState = {
  dismissed: Set<string>;
  overduePresented: Set<string>;
};

type Stored = {
  dismissed: string[];
  overduePresented: string[];
};

function filePath(userId: string): string | null {
  return prefFilePath(`recall.home-nudges.${safePrefUserId(userId)}.json`);
}

function emptyState(): HomeNudgeState {
  return { dismissed: new Set(), overduePresented: new Set() };
}

function parseState(raw: string): HomeNudgeState {
  const parsed = JSON.parse(raw) as unknown;
  if (!parsed || typeof parsed !== "object") return emptyState();
  const row = parsed as Partial<Stored>;
  const dismissed = Array.isArray(row.dismissed)
    ? row.dismissed.filter((id): id is string => typeof id === "string")
    : [];
  const overduePresented = Array.isArray(row.overduePresented)
    ? row.overduePresented.filter((id): id is string => typeof id === "string")
    : [];
  return {
    dismissed: new Set(dismissed),
    overduePresented: new Set(overduePresented),
  };
}

export async function loadHomeNudgeState(userId: string): Promise<HomeNudgeState> {
  const raw = await readPrefFile(filePath(userId));
  if (raw == null) return emptyState();
  try {
    return parseState(raw);
  } catch {
    return emptyState();
  }
}

export async function saveHomeNudgeState(
  userId: string,
  state: HomeNudgeState,
): Promise<void> {
  const stored: Stored = {
    dismissed: [...state.dismissed],
    overduePresented: [...state.overduePresented],
  };
  await writePrefFile(filePath(userId), JSON.stringify(stored));
}

export function pruneHomeNudgeState(
  state: HomeNudgeState,
  openTodoIds: Iterable<string>,
): HomeNudgeState {
  const open = new Set(openTodoIds);
  return {
    dismissed: new Set([...state.dismissed].filter((id) => open.has(id))),
    overduePresented: new Set(
      [...state.overduePresented].filter((id) => open.has(id)),
    ),
  };
}

export async function markHomeOverduePresented(
  userId: string,
  todoIds: string[],
): Promise<HomeNudgeState> {
  if (todoIds.length === 0) return loadHomeNudgeState(userId);
  const state = await loadHomeNudgeState(userId);
  for (const id of todoIds) state.overduePresented.add(id);
  await saveHomeNudgeState(userId, state);
  return state;
}

export async function clearHomeNudgeState(userId: string): Promise<void> {
  await deletePrefFile(filePath(userId));
}

/**
 * Home cards: hide dismissed always. Hide overdue that was already presented
 * in a *previous* session (`sessionOverdueIds` keeps this session's cards up).
 */
export function filterHomeNudgeTodos(
  urgent: HomeUrgentTodo[],
  state: HomeNudgeState,
  sessionOverdueIds: Set<string>,
): HomeUrgentTodo[] {
  return urgent.filter((todo) => {
    if (state.dismissed.has(todo.id)) return false;
    if (
      todo.minutes_until < 0 &&
      state.overduePresented.has(todo.id) &&
      !sessionOverdueIds.has(todo.id)
    ) {
      return false;
    }
    return true;
  });
}
