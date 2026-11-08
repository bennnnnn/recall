import { useCallback, useState } from "react";

import { shareOneAtATime } from "@/lib/shareFile";

/**
 * A Share button's press and its busy state: busy from the tap, through any download, until
 * the sheet closes. A press while any file share runs is dropped (`shareOneAtATime`); a
 * failure is thrown to the caller, which says what went wrong.
 */
export function useFileShare(): { sharing: boolean; share: (task: () => Promise<void>) => Promise<void> } {
  const [sharing, setSharing] = useState(false);
  const share = useCallback(async (task: () => Promise<void>) => {
    await shareOneAtATime(async () => {
      setSharing(true);
      try {
        await task();
      } finally {
        setSharing(false);
      }
    });
  }, []);
  return { sharing, share };
}
