import { ApiRequestError } from "@/lib/api/errorBody";

/**
 * The server has no such item: a chat, a memory fact or a page deleted on another device
 * (or never this account's). Every reader asks this, never the status itself, and takes the
 * item away as its delete would, never as a failure to retry (pre-launch review, 2026-11-27:
 * a chat deleted on the laptop stayed open, and each change to it rolled back against a
 * ghost row).
 */
export function isGone(error: unknown): boolean {
  return error instanceof ApiRequestError && error.status === 404;
}
