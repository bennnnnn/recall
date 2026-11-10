import type { Message } from "@/lib/api";

/**
 * A saved reply whose photo was still on its way at `done` (`photo_pending_until`, set by
 * `markPhotoPending`). The photo comes on the reply's socket (`answer_photo`). When that socket
 * went first (the app in the background, another chat, a network change), the wait outlives it:
 * a read of the chat before the deadline keeps the reply's placeholder (`keepsPendingPhoto`), a
 * kept page holding such a reply is not fresh (`hasPendingPhoto`), and the open chat reads
 * itself once at the deadline (`useChatPendingPhotoRead`), when the saved reply holds the photo
 * if one came.
 */

/** The server's copy of a reply still waiting for its photo: the wait goes on until the photo
 * is in the row or the deadline passes. */
export function keepsPendingPhoto(prior: Message, row: Message, now: number): boolean {
  const until = prior.photo_pending_until;
  return until !== undefined && row.photo_pending_until === undefined && now < until &&
    !row.content.includes("[Image:");
}

/** The thread waits for a late photo (deadline passed or not): a read is still owed. */
export function hasPendingPhoto(messages: readonly Message[]): boolean {
  return messages.some((message) => message.photo_pending_until !== undefined);
}

/** When the thread's last pending photo is due, or null when none is pending. */
export function pendingPhotoDeadline(messages: readonly Message[]): number | null {
  let latest: number | null = null;
  for (const message of messages) {
    const until = message.photo_pending_until;
    if (until !== undefined && (latest === null || until > latest)) latest = until;
  }
  return latest;
}
