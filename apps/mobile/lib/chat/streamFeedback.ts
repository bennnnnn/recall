import { notifySuccess, notifyWarning, selection, tap } from "@/lib/haptics";

export type StreamCue = "activity" | "complete" | "stopped" | "error";

/** One cue per turn. Never per token. */
export function playStreamCue(cue: StreamCue): void {
  if (cue === "activity") selection();
  else if (cue === "complete") notifySuccess();
  else if (cue === "stopped") tap();
  else notifyWarning();
}

export function createStreamCueGate() {
  let heardActivity = false;
  let settled = false;
  return {
    reset() {
      heardActivity = false;
      settled = false;
    },
    activity() {
      if (heardActivity || settled) return;
      heardActivity = true;
      playStreamCue("activity");
    },
    complete() {
      if (settled) return;
      settled = true;
      playStreamCue("complete");
    },
    stopped() {
      if (settled) return;
      settled = true;
      playStreamCue("stopped");
    },
    error() {
      if (settled) return;
      settled = true;
      playStreamCue("error");
    },
  };
}
