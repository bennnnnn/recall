import { useCallback, useState } from "react";

import type { UpgradeSource } from "@/features/billing/components/UpgradeSheet";

/**
 * The plans sheet over the chat and where it was opened from (analytics only). The composer's
 * mic, a picture, live talk, the quota nudge and the welcome offer all open this one sheet.
 */
export function useUpgradeSheet() {
  const [visible, setVisible] = useState(false);
  const [source, setSource] = useState<UpgradeSource>("other");
  const open = useCallback((from: UpgradeSource = "other") => {
    setSource(from);
    setVisible(true);
  }, []);
  const close = useCallback(() => setVisible(false), []);
  return { visible, source, open, close };
}
