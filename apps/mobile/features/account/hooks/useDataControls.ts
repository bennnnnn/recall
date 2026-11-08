import { useRef, useState } from "react";

import { useAuth } from "@/contexts/AuthContext";
import { type AccountDeleteOutcome, useAccountDelete } from "@/hooks/useAccountDelete";
import { api } from "@/lib/api";
import { formatExportJsonForShare, shareAccountExport } from "@/lib/exportData";
import { shareOneAtATime } from "@/lib/shareFile";

type DataControlsProgress = "idle" | "exporting" | "deleting";

export function useDataControls() {
  const { token } = useAuth();
  const deleteAndSignOut = useAccountDelete();
  const [progress, setProgress] = useState<DataControlsProgress>("idle");
  const exportAbort = useRef<AbortController | null>(null);

  /** Resolves false when the export was cancelled. */
  const exportData = async (): Promise<boolean> => {
    if (!token || progress !== "idle") return false;
    const controller = new AbortController();
    exportAbort.current = controller;
    setProgress("exporting");
    try {
      const raw = await api.exportDataText(token, controller.signal);
      if (controller.signal.aborted) return false;
      // Cancel lets a new export start while the last one's sheet may still be open.
      return await shareOneAtATime(() => shareAccountExport(formatExportJsonForShare(raw)));
    } catch (error) {
      if (controller.signal.aborted) return false;
      throw error;
    } finally {
      if (exportAbort.current === controller) exportAbort.current = null;
      setProgress("idle");
    }
  };

  const cancelExport = () => {
    exportAbort.current?.abort();
    setProgress("idle");
  };

  const deleteAccount = async (): Promise<AccountDeleteOutcome> => {
    if (!token || progress !== "idle") return "failed";
    const outcome = await deleteAndSignOut(() => setProgress("deleting"));
    if (outcome === "failed" || outcome === "unavailable") setProgress("idle");
    return outcome;
  };

  return { token, progress, exportData, cancelExport, deleteAccount };
}
