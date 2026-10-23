import { useState } from "react";

import { useAuth } from "@/contexts/AuthContext";
import { useTodosOptional } from "@/features/todos/context/TodosContext";
import { allowReminderAlerts } from "@/features/todos/model/reminderAlerts";
import {
  isProposalSaved,
  markProposalSaved,
  type ReminderProposal,
} from "@/features/todos/model/reminderProposal";
import { api, type Todo } from "@/lib/api";

type ReminderProposalError = "expired" | "changed" | "failed";

/** `rows` with the saved rows in place (new ones first) and the deleted ones gone. */
export function applySavedRows(rows: Todo[], saved: Todo[], deletedIds: string[]): Todo[] {
  const gone = new Set(deletedIds);
  const byId = new Map(saved.map((row) => [row.id, row]));
  const kept = rows.filter((row) => !gone.has(row.id)).map((row) => byId.get(row.id) ?? row);
  const known = new Set(rows.map((row) => row.id));
  return [...saved.filter((row) => !known.has(row.id)), ...kept];
}

/** Saves a chat reminder card on tap, then refreshes To-do and its notifications. */
export function useReminderProposal(proposal: ReminderProposal) {
  const { token } = useAuth();
  const todos = useTodosOptional();
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(() => isProposalSaved(proposal));
  const [error, setError] = useState<ReminderProposalError | null>(null);
  const [alertsOff, setAlertsOff] = useState(false);

  const confirm = async () => {
    if (!token || busy || done) return;
    setBusy(true);
    setError(null);
    try {
      const saved = await api.confirmReminderProposal(token, proposal.proposalId);
      markProposalSaved(proposal.proposalId);
      setDone(true);
      // Ask before the rows land, so the reminder sync that follows may schedule its alert.
      if (proposal.items.some((item) => item.dueAt && (item.action === "add" || item.action === "set_due"))) {
        setAlertsOff((await allowReminderAlerts()) === "off");
      }
      // The rows the tap wrote, applied as they are (code-health audit NET-16); a card
      // another device saved first sends none, and the list is read again.
      if (saved.todos) todos?.setTodos((rows) => applySavedRows(rows, saved.todos ?? [], saved.deleted_ids));
      else void todos?.refresh({ silent: true, force: true });
    } catch (caught) {
      // ApiRequestError carries the HTTP status: 410 expired, 409 changed since.
      const status = (caught as { status?: unknown } | null)?.status;
      setError(status === 410 ? "expired" : status === 409 ? "changed" : "failed");
    } finally {
      setBusy(false);
    }
  };

  return { busy, done: done || isProposalSaved(proposal), error, alertsOff, confirm };
}
