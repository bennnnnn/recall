import { useState } from "react";

import { useAuthToken } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import type { CalendarProposal } from "@/lib/calendarProposal";

export function useCalendarProposal(proposal: CalendarProposal) {
  const token = useAuthToken();
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const confirm = async () => {
    if (!token || busy || done) return false;
    setBusy(true);
    try {
      let proposalId = proposal.proposal_id;
      if (!proposalId) {
        const created = await api.proposeCalendarEvent(token, {
          title: proposal.title,
          start_at: proposal.start_at,
          end_at: proposal.end_at,
          location: proposal.location ?? undefined,
          description: proposal.description ?? undefined,
        });
        proposalId = created.proposal_id;
      }
      await api.confirmCalendarEvent(token, proposalId);
      setDone(true);
      return true;
    } catch {
      return false;
    } finally {
      setBusy(false);
    }
  };

  return { busy, done, confirm };
}
