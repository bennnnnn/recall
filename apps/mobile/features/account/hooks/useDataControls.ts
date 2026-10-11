import { useState } from "react";

import { useAuth } from "@/contexts/AuthContext";
import { isAccountDeleteComplete } from "@/lib/accountDelete";
import { api } from "@/lib/api";
import { formatExportJsonForShare, shareAccountExport } from "@/lib/exportData";

export type DataControlsProgress = "idle" | "exporting" | "deleting";

export function useDataControls() {
  const { token, signOut, setIgnoreUnauthorized } = useAuth();
  const [progress, setProgress] = useState<DataControlsProgress>("idle");

  const exportData = async () => {
    if (!token || progress !== "idle") return;
    setProgress("exporting");
    try {
      const raw = await api.exportDataText(token);
      await shareAccountExport(formatExportJsonForShare(raw));
    } finally {
      setProgress("idle");
    }
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

  return { token, progress, exportData, deleteAccount };
}
