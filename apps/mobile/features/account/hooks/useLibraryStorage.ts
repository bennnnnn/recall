import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";

import { useAuth } from "@/contexts/AuthContext";
import { attachmentsApi } from "@/features/attachments/api";
import { getSessionGeneration } from "@/lib/auth";
import { reportFailure } from "@/lib/sentry";

type LibraryStorage = { usedBytes: number; limitBytes: number };

/**
 * What the account keeps in Library against its plan's total, read each time the screen
 * shows: a file deleted in Library, or a plan bought, shows on the way back. Another
 * account's or plan's numbers are never shown.
 */
export function useLibraryStorage(): LibraryStorage | null {
  const { token, user } = useAuth();
  const key = `${getSessionGeneration()}:${user?.id ?? ""}:${user?.plan ?? ""}`;
  const [read, setRead] = useState<{ key: string; storage: LibraryStorage } | null>(null);

  useFocusEffect(
    useCallback(() => {
      if (!token) return;
      let current = true;
      attachmentsApi
        .getLibraryStorage(token)
        .then((r) => {
          if (current) setRead({ key, storage: { usedBytes: r.used_bytes, limitBytes: r.limit_bytes } });
        })
        .catch((error: unknown) => reportFailure("library_storage", error));
      return () => {
        current = false;
      };
    }, [token, key]),
  );

  return read?.key === key ? read.storage : null;
}
