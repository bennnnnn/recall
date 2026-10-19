import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { agreeToAiDataSharing } from "@/lib/api";
import { writeCachedUser } from "@/lib/cachedUser";
import { tap } from "@/lib/haptics";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

type ConsentChoice = "agree" | "decline";

/** Agree (stored on the account, so every device knows) or leave by signing out. */
export function useAiConsentActions() {
  const { token, mergeUser, signOut } = useAuth();
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const busyRef = useRef(false);
  const [busy, setBusy] = useState<ConsentChoice | null>(null);

  const run = useCallback(
    async (choice: ConsentChoice, action: () => Promise<void>) => {
      if (busyRef.current) return;
      tap();
      busyRef.current = true;
      setBusy(choice);
      try {
        await action();
      } catch {
        reportRecoverableError(feedback, t("onboarding.consent_failed"));
      } finally {
        busyRef.current = false;
        setBusy(null);
      }
    },
    [feedback, t],
  );

  const agree = useCallback(
    () =>
      run("agree", async () => {
        if (!token) return;
        const updated = await agreeToAiDataSharing(token);
        // The screen's own gate then sends the user on to the chat.
        mergeUser(updated);
        void writeCachedUser(updated);
      }),
    [mergeUser, run, token],
  );

  const decline = useCallback(() => run("decline", signOut), [run, signOut]);

  return { busy, agree, decline };
}
