import { useRef, useState } from "react";

import { useAuth } from "@/contexts/AuthContext";
import { isAccountDeleteComplete } from "@/lib/accountDelete";
import { api } from "@/lib/api";
import { formatExportJsonForShare, shareAccountExport } from "@/lib/exportData";

type DataControlsProgress = "idle" | "exporting" | "deleting";

export function useDataControls() {
  const { token, signOut, setIgnoreUnauthorized } = useAuth();
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
      await shareAccountExport(formatExportJsonForShare(raw));
      return true;
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

  const deleteAccount = async () => {
    if (!token || progress !== "idle") return false;
    setProgress("deleting");
    setIgnoreUnauthorized(true);
    try {
      try {
        await api.deleteAccount(token);
      } catch (error) {
        if (!isAccountDeleteComplete(error)) throw error;
      }
      await signOut();
      return true;
    } catch {
      setIgnoreUnauthorized(false);
      setProgress("idle");
      return false;
    }
  };

  return { token, progress, exportData, cancelExport, deleteAccount };
}
