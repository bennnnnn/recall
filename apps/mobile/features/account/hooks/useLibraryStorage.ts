import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";

import { useAccountSession } from "@/contexts/accountSession";
import { useAuth } from "@/contexts/AuthContext";
import { attachmentsApi } from "@/features/attachments/api";
import { useReconnectRefresh } from "@/hooks/useReconnectRefresh";
import { getSessionGeneration } from "@/lib/auth";
import { reportFailure } from "@/lib/sentry";

type LibraryStorage = { usedBytes: number; limitBytes: number };

/**
 * What the account keeps in Library against its plan's total, read each time the screen
 * shows (a file deleted in Library, or a plan bought, shows on the way back) and once when
 * the API answers after an outage. Keyed on the account, never the token: the hourly token
 * rotation reads nothing again (NET-11). Another account's or plan's numbers are never shown.
 */
export function useLibraryStorage(): LibraryStorage | null {
  const { account, getToken } = useAccountSession();
  const { user } = useAuth();
  const key = `${getSessionGeneration()}:${account ?? ""}:${user?.plan ?? ""}`;
  const [read, setRead] = useState<{ key: string; storage: LibraryStorage } | null>(null);
  const readAtRef = useRef<number | undefined>(undefined);
  // The account and plan now: a read made under another lands nowhere.
  const keyRef = useRef(key);
  useEffect(() => {
    keyRef.current = key;
  }, [key]);
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const load = useCallback(() => {
    const token = getToken();
    if (!account || !token) return;
    attachmentsApi
      .getLibraryStorage(token)
      .then((r) => {
        // An answer for another account or plan (it changed while this read was out) is not
        // this screen's: it neither shows nor counts as the read since an outage.
        if (!mountedRef.current || keyRef.current !== key) return;
        readAtRef.current = Date.now();
        setRead({ key, storage: { usedBytes: r.used_bytes, limitBytes: r.limit_bytes } });
      })
      .catch((error: unknown) => reportFailure("library_storage", error));
  }, [account, getToken, key]);

  useFocusEffect(load);
  useReconnectRefresh(load, { readAt: () => readAtRef.current });

  return read?.key === key ? read.storage : null;
}
