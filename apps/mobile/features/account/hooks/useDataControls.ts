import { useRef, useState } from "react";
import { Platform } from "react-native";

import { useAuth } from "@/contexts/AuthContext";
import { isAccountDeleteComplete } from "@/lib/accountDelete";
import { api } from "@/lib/api";
import { appleConsentForAccountDelete } from "@/lib/apple-auth";
import { formatExportJsonForShare, shareAccountExport } from "@/lib/exportData";

type DataControlsProgress = "idle" | "exporting" | "deleting";

/** "cancelled": the user closed the Sign in with Apple sheet, so nothing was deleted. */
type AccountDeleteOutcome = "deleted" | "cancelled" | "failed";

export function useDataControls() {
  const { token, user, signOut, setIgnoreUnauthorized } = useAuth();
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

  /** An Apple-linked account on iOS asks Apple first, so the server can revoke the grant. */
  const appleCodeForDelete = async (): Promise<string | null | "cancelled"> => {
    if (Platform.OS !== "ios" || !user?.apple_linked) return null;
    const consent = await appleConsentForAccountDelete();
    if (consent.kind === "cancelled") return "cancelled";
    return consent.kind === "code" ? consent.code : null;
  };

  const deleteAccount = async (): Promise<AccountDeleteOutcome> => {
    if (!token || progress !== "idle") return "failed";
    const appleCode = await appleCodeForDelete();
    if (appleCode === "cancelled") return "cancelled";
    setProgress("deleting");
    setIgnoreUnauthorized(true);
    try {
      try {
        await api.deleteAccount(token, appleCode);
      } catch (error) {
        if (!isAccountDeleteComplete(error)) throw error;
      }
      await signOut();
      return "deleted";
    } catch {
      setIgnoreUnauthorized(false);
      setProgress("idle");
      return "failed";
    }
  };

  return { token, progress, exportData, cancelExport, deleteAccount };
}
