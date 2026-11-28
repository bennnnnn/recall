/**
 * The file a chat send is uploading: how far it has got and its Cancel. The composer's
 * send button turns into Cancel while it runs and its status line says the percent
 * (`useSendUpload`); a cancelled upload gives the draft back (useChatSendRoute).
 */
import type { Translate } from "@/lib/i18n/translate";
import { createValueStore } from "@/lib/listenerSet";

export type SendUpload = {
  /** 0–1 once the phone knows the file's size, else null. */
  progress: number | null;
  cancel: () => void;
};

/** What the upload reports to, and stops by. */
type UploadTransfer = {
  signal: AbortSignal;
  onProgress: (fraction: number) => void;
};

const current = createValueStore<SendUpload | null>(null);

export const sendUploadStore = { get: current.get, subscribe: current.subscribe };

/** The composer's status line while a send waits: its location, or how far its file has got. */
export function sendStatusLine(phase: string, upload: SendUpload | null, t: Translate): string | undefined {
  if (phase === "locating") return t("chat.locating");
  if (!upload) return undefined;
  if (upload.progress === null) return t("chat.uploading");
  return t("chat.uploading_percent", { percent: Math.floor(upload.progress * 100) });
}

/** Starts the one upload the composer shows; `finish` once it settles, however it ends. */
export function startSendUpload(): UploadTransfer & { finish: () => void } {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  const mine = () => current.get()?.cancel === cancel;
  current.set({ progress: null, cancel });
  return {
    signal: controller.signal,
    onProgress(fraction) {
      const progress = Math.min(1, Math.max(0, fraction));
      const shown = current.get();
      // In whole percent: the status line redraws only when its number changes.
      if (mine() && Math.floor((shown?.progress ?? -1) * 100) !== Math.floor(progress * 100)) {
        current.set({ progress, cancel });
      }
    },
    finish() {
      if (mine()) current.set(null);
    },
  };
}
