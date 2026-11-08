/**
 * A purchase the store holds for approval or payment (Ask to Buy, a Play slow payment, a
 * bank's check): the plan it was for, and since when. While one waits, no second purchase
 * is offered.
 *
 * On Android that is what keeps a second charge away: Pro bought while Plus waits starts a
 * separate subscription (a purchase replaces only an active Plus), and both are charged once
 * Plus clears, which a slow payment can take days to do. So there the hold is kept on disk
 * for its account, through relaunches, for up to a week. On iOS both plans share one
 * subscription group, so the hold is the session's and lets go after 30 minutes.
 *
 * RevenueCat reports neither a declined Ask to Buy nor a payment never made, so a hold ends
 * when the store grants a plan, the user restores purchases, it expires, or the account
 * signs out.
 */
import { Platform } from "react-native";

import { cacheFile } from "@/lib/cache/cacheFile";
import { createValueStore } from "@/lib/listenerSet";
import { PLAN_RANK, type PaidPlanId, type PlanId } from "@/lib/plan";

type Hold = { plan: PaidPlanId; since: number };

const held = createValueStore<Hold | null>(null);
/** Android's hold across launches: "account|plan|since". */
const heldFile = cacheFile("recall-held-purchase.txt");

const ANDROID_HOLD_MS = 7 * 24 * 60 * 60_000;
const IOS_HOLD_MS = 30 * 60_000;

function holdMs(): number {
  return Platform.OS === "android" ? ANDROID_HOLD_MS : IOS_HOLD_MS;
}

export const subscribeHeldPurchase = held.subscribe;

/** The plan a held purchase is for, or null. */
export function heldPurchase(): PaidPlanId | null {
  return held.get()?.plan ?? null;
}

export function holdPurchase(account: string, plan: PaidPlanId, now: number = Date.now()): void {
  held.set({ plan, since: now });
  if (Platform.OS === "android") void heldFile.write([account, plan, now].join("|"));
}

/** Lets go of the hold, here and on disk (a restore, a sign-out). */
export function releaseHeldPurchase(): Promise<void> {
  held.set(null);
  return heldFile.clear();
}

/** The store grants `plan`: a purchase waiting for that plan or a lower one has gone through. */
export function settleHeldPurchase(plan: PlanId): void {
  const waiting = held.get();
  if (waiting && PLAN_RANK[plan] >= PLAN_RANK[waiting.plan]) void releaseHeldPurchase();
}

/** A hold older than its platform allows lets go. */
export function expireHeldPurchase(now: number = Date.now()): void {
  const waiting = held.get();
  if (waiting && now - waiting.since >= holdMs()) void releaseHeldPurchase();
}

/**
 * As the store is set up for `account`, before anything can be bought: its hold from an
 * earlier launch while still due. One for another account (a sign-out that could not clear
 * it) or past its time is deleted.
 */
export async function loadHeldPurchase(account: string, now: number = Date.now()): Promise<void> {
  const raw = await heldFile.read();
  if (raw === null) return;
  const [owner, plan, since] = raw.split("|");
  const at = Number(since);
  const due = owner === account && (plan === "plus" || plan === "pro") && Number.isFinite(at) && now - at < holdMs();
  if (due) held.set({ plan, since: at });
  else await heldFile.clear();
}
