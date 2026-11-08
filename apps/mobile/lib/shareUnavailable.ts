/** A file share this build cannot make, kept free of React Native so pure modules can read it. */

/** This build cannot hand a file to the share sheet (Android without expo-sharing): an app update fixes it. */
export class SharingUnavailableError extends Error {
  constructor() {
    super("Sharing files needs an app update.");
    this.name = "SharingUnavailableError";
  }
}

/** A file share asked for while another is still running (`shareOneAtATime`): nothing was tried. */
export class ShareInProgressError extends Error {
  constructor() {
    super("A share is already in progress.");
    this.name = "ShareInProgressError";
  }
}

/**
 * The words for a failed file share: an update for a build that cannot share files, "already
 * sharing" for one asked for during another, else the caller's own line (null: its default).
 * Each screen that shares a file reads it, so none shows its generic line where it is wrong.
 */
export function shareFailureKey<Fallback extends string | null>(error: unknown, fallbackKey: Fallback): string | Fallback {
  if (error instanceof SharingUnavailableError) return "common.share_needs_update";
  return error instanceof ShareInProgressError ? "common.share_in_progress" : fallbackKey;
}
