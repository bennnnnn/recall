import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";

import { useAuth } from "@/contexts/AuthContext";
import { attachmentsApi } from "@/features/attachments/api";
import { useReconnectRefresh } from "@/hooks/useReconnectRefresh";
import { getSessionGeneration } from "@/lib/auth";
import { reportFailure } from "@/lib/sentry";

type LibraryStorage = { usedBytes: number; limitBytes: number };

/**
 * What the account keeps in Library against its plan's total, read each time the screen
 * shows (a file deleted in Library, or a plan bought, shows on the way back) and once when
 * the API answers after an outage. Another account's or plan's numbers are never shown.
 */
export function useLibraryStorage(): LibraryStorage | null {
  const { token, user } = useAuth();
  const key = `${getSessionGeneration()}:${user?.id ?? ""}:${user?.plan ?? ""}`;
  const [read, setRead] = useState<{ key: string; storage: LibraryStorage } | null>(null);
  const readAtRef = useRef<number | undefined>(undefined);
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const load = useCallback(() => {
    if (!token) return;
    attachmentsApi
      .getLibraryStorage(token)
      .then((r) => {
        readAtRef.current = Date.now();
        // Kept under the account and plan it was read for: the return shows it only for those.
        if (mountedRef.current) {
          setRead({ key, storage: { usedBytes: r.used_bytes, limitBytes: r.limit_bytes } });
        }
      })
      .catch((error: unknown) => reportFailure("library_storage", error));
  }, [token, key]);

  useFocusEffect(load);
  useReconnectRefresh(load, { readAt: () => readAtRef.current });

  return read?.key === key ? read.storage : null;
}
