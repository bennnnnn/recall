import { useState } from "react";

import { useAuth } from "@/contexts/AuthContext";
import { useTodosOptional } from "@/features/todos/context/TodosContext";
import {
  isProposalSaved,
  markProposalSaved,
  type ReminderProposal,
} from "@/features/todos/model/reminderProposal";
import { api } from "@/lib/api";

type ReminderProposalError = "expired" | "changed" | "failed";

/** Saves a chat reminder card on tap, then refreshes To-do and its notifications. */
export function useReminderProposal(proposal: ReminderProposal) {
  const { token } = useAuth();
  const todos = useTodosOptional();
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(() => isProposalSaved(proposal));
  const [error, setError] = useState<ReminderProposalError | null>(null);

  const confirm = async () => {
    if (!token || busy || done) return;
    setBusy(true);
    setError(null);
    try {
      await api.confirmReminderProposal(token, proposal.proposalId);
      markProposalSaved(proposal.proposalId);
      setDone(true);
      void todos?.refresh({ silent: true, force: true });
    } catch (caught) {
      // ApiRequestError carries the HTTP status: 410 expired, 409 changed since.
      const status = (caught as { status?: unknown } | null)?.status;
      setError(status === 410 ? "expired" : status === 409 ? "changed" : "failed");
    } finally {
      setBusy(false);
    }
  };

  return { busy, done: done || isProposalSaved(proposal), error, confirm };
}
