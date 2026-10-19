import NetInfo from "@react-native-community/netinfo";

import { api } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { isNetworkOffline } from "@/lib/networkStatus";

export type AttachmentIndexStatus = { indexed: boolean; failed: boolean };

export const INDEX_READY: AttachmentIndexStatus = Object.freeze({ indexed: true, failed: false });
export const INDEX_PENDING: AttachmentIndexStatus = Object.freeze({ indexed: false, failed: false });
const INDEX_FAILED: AttachmentIndexStatus = Object.freeze({ indexed: false, failed: true });

const FIRST_POLL_DELAY_MS = 2000;
const MAX_POLL_DELAY_MS = 15_000;
const POLL_BACKOFF = 1.5;
/** Match jobs.py `_JOB_DONE_CLAIM_TTL_SECONDS` (300s) plus one poll slack. */
export const INDEX_POLL_MAX_MS = 360_000;
/**
 * An attachment older than this has had its indexing job run (or give up),
 * so its first answer is final. Well past INDEX_POLL_MAX_MS so a phone clock
 * that runs a few minutes ahead never fails a fresh upload.
 */
const INDEX_SETTLED_AGE_MS = 15 * 60_000;

/** One status per attachment, however many rows show it or remount. */
type Poller = {
  id: string;
  token: string;
  status: AttachmentIndexStatus;
  settled: boolean;
  startedAt: number | null;
  delay: number;
  timer: ReturnType<typeof setTimeout> | undefined;
  inFlight: boolean;
  listeners: Set<() => void>;
};

const pollers = new Map<string, Poller>();
let generation: number | null = null;
let offline = false;
let stopWatchingNetwork: (() => void) | null = null;

function settledByAge(createdAt: string | undefined): boolean {
  const created = createdAt ? Date.parse(createdAt) : Number.NaN;
  return Number.isFinite(created) && Date.now() - created >= INDEX_SETTLED_AGE_MS;
}

/** Another account's statuses (and timers) go with the session that read them. */
function current(): Map<string, Poller> {
  const session = getSessionGeneration();
  if (generation !== session) {
    pollers.forEach(pause);
    pollers.clear();
    generation = session;
  }
  return pollers;
}

function waiting(poller: Poller): boolean {
  return !poller.settled && poller.listeners.size > 0;
}

function pause(poller: Poller): void {
  if (poller.timer !== undefined) clearTimeout(poller.timer);
  poller.timer = undefined;
}

function publish(poller: Poller, status: AttachmentIndexStatus, settled = false): void {
  poller.settled = settled;
  if (poller.status === status) return;
  poller.status = status;
  poller.listeners.forEach((listener) => listener());
}

function resume(poller: Poller): void {
  if (waiting(poller) && poller.timer === undefined && !poller.inFlight) void poll(poller);
}

function schedule(poller: Poller): void {
  // Offline, the next reconnect resumes it; with nothing on screen, the next mount does.
  if (!waiting(poller) || offline) return;
  poller.timer = setTimeout(() => {
    poller.timer = undefined;
    void poll(poller);
  }, poller.delay);
  poller.delay = Math.min(MAX_POLL_DELAY_MS, poller.delay * POLL_BACKOFF);
}

async function poll(poller: Poller): Promise<void> {
  if (!waiting(poller) || offline) return;
  const session = generation;
  poller.inFlight = true;
  poller.startedAt ??= Date.now();
  try {
    const row = await api.getAttachmentUrl(poller.token, poller.id);
    if (session !== generation) return;
    if (row.indexed !== false) publish(poller, INDEX_READY, true);
    // A file with no extractable text stays unindexed forever: one answer is enough.
    else if (settledByAge(row.created_at)) publish(poller, INDEX_FAILED, true);
  } catch {
    // Still pending; the backoff spaces out the next try.
  } finally {
    poller.inFlight = false;
  }
  if (session !== generation || poller.settled) return void watchNetwork();
  if (Date.now() - poller.startedAt >= INDEX_POLL_MAX_MS) {
    publish(poller, INDEX_FAILED, true);
    return void watchNetwork();
  }
  schedule(poller);
}

/** Listen for reconnects only while some status is still waiting on the server. */
function watchNetwork(): void {
  const needed = [...pollers.values()].some(waiting);
  if (!needed) {
    stopWatchingNetwork?.();
    stopWatchingNetwork = null;
    offline = false;
    return;
  }
  if (stopWatchingNetwork) return;
  stopWatchingNetwork = NetInfo.addEventListener((state) => {
    const wasOffline = offline;
    offline = isNetworkOffline(state);
    if (wasOffline && !offline) pollers.forEach(resume);
  });
}

export function readAttachmentIndexStatus(attachmentId: string): AttachmentIndexStatus {
  return current().get(attachmentId)?.status ?? INDEX_PENDING;
}

export function subscribeAttachmentIndexStatus(
  attachmentId: string,
  token: string,
  listener: () => void,
): () => void {
  const map = current();
  let poller = map.get(attachmentId);
  if (!poller) {
    poller = {
      id: attachmentId, token, status: INDEX_PENDING, settled: false, startedAt: null,
      delay: FIRST_POLL_DELAY_MS, timer: undefined, inFlight: false, listeners: new Set(),
    };
    map.set(attachmentId, poller);
  }
  const subscribed = poller;
  subscribed.token = token;
  subscribed.listeners.add(listener);
  watchNetwork();
  resume(subscribed);
  return () => {
    subscribed.listeners.delete(listener);
    if (!subscribed.listeners.size) pause(subscribed);
    watchNetwork();
  };
}

/** Test helper — forget every status between cases. */
export function resetAttachmentIndexStatus(): void {
  pollers.forEach(pause);
  pollers.clear();
  generation = null;
  stopWatchingNetwork?.();
  stopWatchingNetwork = null;
  offline = false;
}
