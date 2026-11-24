import { Platform } from "react-native";

import type { PurchasesPackage } from "react-native-purchases";

import {
  expireHeldPurchase,
  heldPurchase,
  holdPurchase,
  loadHeldPurchase,
  releaseHeldPurchase,
  settleHeldPurchase,
} from "@/features/billing/model/heldPurchase";
import { isExpoGo } from "@/lib/expoRuntime";
import { createValueStore } from "@/lib/listenerSet";
import type { PaidPlanId, PlanId } from "@/lib/plan";
import { reportFailure } from "@/lib/sentry";

/** The one paid plan's RevenueCat entitlement; the server maps the same id. */
const PRO_ENTITLEMENT_ID = "pro";

/** How often the plan is paid for: the offering's standard monthly and annual packages. */
export type BillingPeriod = "monthly" | "yearly";
export const BILLING_PERIODS: readonly BillingPeriod[] = ["monthly", "yearly"];

/** Opaque handle — keeps react-native-purchases out of the static import graph
 * (its types are erased at build time). */
export type PlanPackage = {
  plan: PaidPlanId;
  period: BillingPeriod;
  /** Localized by the store ("$7.99", "7,99 €"); never hardcoded. */
  priceString: string;
  /** The same price as a number, in the store's currency: only to compare the periods. */
  price: number;
  /** The store's own per-month figure for the price ("$5.00" for $59.99 a year). */
  pricePerMonth?: string | null;
  productId: string;
  native: PurchasesPackage;
  /** A free first period the store gives this account; none when it gives none. */
  trial?: FreeTrial;
};

/** A free first period: "7 days", "1 month". `priceString` is the store's zero ("$0.00"). */
export type FreeTrial = { count: number; unit: "day" | "week" | "month" | "year"; priceString: string };

type IntroPrice = PurchasesPackage["product"]["introPrice"];
const TRIAL_UNITS = { DAY: "day", WEEK: "week", MONTH: "month", YEAR: "year" } as const;

/** The store's introductory price as a free trial, or none when it costs anything. */
export function freeTrialOf(intro: IntroPrice): FreeTrial | undefined {
  if (!intro || intro.price !== 0) return undefined;
  const unit = TRIAL_UNITS[intro.periodUnit as keyof typeof TRIAL_UNITS];
  const count = intro.periodNumberOfUnits * Math.max(1, intro.cycles);
  if (!unit || !(count > 0)) return undefined;
  return { count, unit, priceString: intro.priceString };
}

type ActiveEntitlements = Record<string, unknown>;
type CustomerInfoLike = { entitlements: { active: ActiveEntitlements } };

type PurchasesModule = typeof import("react-native-purchases");

let purchasesModule: PurchasesModule | null | undefined;

function revenueCatApiKey(): string | null {
  if (Platform.OS === "ios") {
    const key = process.env.EXPO_PUBLIC_REVENUECAT_IOS_API_KEY?.trim();
    return key || null;
  }
  if (Platform.OS === "android") {
    const key = process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY?.trim();
    return key || null;
  }
  return null;
}

export function isPurchasesConfigured(): boolean {
  if (isExpoGo()) return false;
  return revenueCatApiKey() != null;
}

export function isPurchaseCancelled(error: unknown): boolean {
  return Boolean(
    error &&
      typeof error === "object" &&
      "userCancelled" in error &&
      error.userCancelled === true,
  );
}

/** The plan the store says is active (what the server will also find). */
export function planFromCustomerInfo(info: CustomerInfoLike): PlanId {
  return info.entitlements.active[PRO_ENTITLEMENT_ID] != null ? "pro" : "free";
}

async function loadPurchases(): Promise<PurchasesModule | null> {
  if (purchasesModule !== undefined) return purchasesModule;
  if (!isPurchasesConfigured()) {
    purchasesModule = null;
    return null;
  }
  try {
    purchasesModule = await import("react-native-purchases");
    return purchasesModule;
  } catch (error) {
    // A configured build without the store's native module: no plan can be bought.
    reportFailure("store", error);
    purchasesModule = null;
    return null;
  }
}

/** App user id RevenueCat is set up for in this process (configure runs once). */
let configuredAppUserId: string | null = null;

/**
 * RevenueCat answers no read before it is set up for the signed-in account, and that waits
 * for the server to confirm the account: a read before then came back "store unavailable".
 * True once the set-up has run, whatever it found (a failure then is the store's own).
 */
const storeSetUp = createValueStore(false);

/** Raised by each sign-out: a set-up still running for the account that left records nothing. */
let setupGeneration = 0;

export const subscribeStoreReady = storeSetUp.subscribe;

/** The store can be read now: set up for this account, or not in this build at all. */
export function isStoreReady(): boolean {
  return !isPurchasesConfigured() || storeSetUp.get();
}

export async function configurePurchases(appUserId: string): Promise<void> {
  const generation = setupGeneration;
  const current = () => generation === setupGeneration;
  const mod = await loadPurchases();
  const apiKey = revenueCatApiKey();
  if (!mod || !apiKey) {
    // Nothing to set up: each read reports the store unavailable.
    if (current()) storeSetUp.set(true);
    return;
  }
  if (configuredAppUserId === appUserId) return;
  try {
    if (configuredAppUserId == null) {
      mod.default.setLogLevel(__DEV__ ? mod.LOG_LEVEL.DEBUG : mod.LOG_LEVEL.WARN);
      await mod.default.configure({ apiKey, appUserID: appUserId });
    } else {
      // A second configure is unsupported; switching accounts is a logIn.
      await mod.default.logIn(appUserId);
    }
    // Signed out meanwhile: the store was logged out, so the next sign-in logs in again.
    configuredAppUserId = current() ? appUserId : "";
  } finally {
    if (current()) {
      // An Android hold from an earlier launch is in place before anything can be bought.
      await loadHeldPurchase(appUserId);
      if (current()) storeSetUp.set(true);
    }
  }
}

/**
 * Reads the store again for a held purchase (`heldPurchase.ts`), as the sheet opens and as
 * the app comes back: one the store now grants is done, and one past its time lets go.
 * Never rejects.
 */
export async function recheckPendingPurchase(now: number = Date.now()): Promise<void> {
  if (!heldPurchase()) return;
  const mod = await loadPurchases();
  if (!mod) return;
  try {
    settleHeldPurchase(planFromCustomerInfo(await mod.default.getCustomerInfo()));
  } catch (error) {
    reportFailure("store", error);
  }
  expireHeldPurchase(now);
}

export type PlanOffer = {
  packages: Partial<Record<BillingPeriod, PlanPackage>>;
  /** The store could not be read, or sells no plan: say so and offer a retry. */
  unavailable: boolean;
};

const STORE_UNAVAILABLE: PlanOffer = { packages: {}, unavailable: true };

/** A store that answered and sells nothing. The report drops an error's text; its code says which. */
function storeSellsNothing(code: "no_current_offering" | "no_plan_in_offering"): Error {
  return Object.assign(new Error(`The store sells no plan: ${code}`), { code });
}

/**
 * The store's packages for the paid plan in the current offering, by billing period. A failed read
 * is `unavailable`, never an empty offer that looks like "no products".
 */
export async function getPlanPackages(): Promise<PlanOffer> {
  const mod = await loadPurchases();
  if (!mod) return STORE_UNAVAILABLE;
  let offerings: Awaited<ReturnType<PurchasesModule["default"]["getOfferings"]>>;
  try {
    offerings = await mod.default.getOfferings();
  } catch (error) {
    reportFailure("store", error);
    return STORE_UNAVAILABLE;
  }
  const offering = offerings.current;
  if (!offering) {
    reportFailure("store", storeSellsNothing("no_current_offering"));
    return STORE_UNAVAILABLE;
  }
  const found: Partial<Record<BillingPeriod, PlanPackage>> = {};
  const periods: [BillingPeriod, PurchasesPackage | null][] = [
    ["monthly", offering.monthly],
    ["yearly", offering.annual],
  ];
  for (const [period, pkg] of periods) {
    if (!pkg) continue;
    found[period] = {
      plan: "pro",
      period,
      priceString: pkg.product.priceString,
      price: pkg.product.price,
      pricePerMonth: pkg.product.pricePerMonthString,
      productId: pkg.product.identifier,
      native: pkg,
    };
  }
  if (!found.monthly && !found.yearly) {
    reportFailure("store", storeSellsNothing("no_plan_in_offering"));
    return STORE_UNAVAILABLE;
  }
  await addFreeTrials(mod, Object.values(found));
  return { packages: found, unavailable: false };
}

/**
 * A free trial is promised only to an account that gets it. Google lists a trial offer only
 * to an account it is open to; the App Store lists it to everyone, so iOS asks the store, and
 * an answer other than eligible (or no answer) shows the plain price.
 */
async function addFreeTrials(mod: PurchasesModule, packages: PlanPackage[]): Promise<void> {
  const offered = packages.filter((pkg) => freeTrialOf(pkg.native.product.introPrice));
  if (offered.length === 0) return;
  let eligible = (_productId: string) => true;
  if (Platform.OS === "ios") {
    try {
      const status = await mod.default.checkTrialOrIntroductoryPriceEligibility(
        offered.map((pkg) => pkg.productId),
      );
      const yes = mod.default.INTRO_ELIGIBILITY_STATUS.INTRO_ELIGIBILITY_STATUS_ELIGIBLE;
      eligible = (productId) => status[productId]?.status === yes;
    } catch (error) {
      reportFailure("store", error);
      return;
    }
  }
  for (const pkg of offered) {
    if (eligible(pkg.productId)) pkg.trial = freeTrialOf(pkg.native.product.introPrice);
  }
}

/** RevenueCat rejects a purchase the store holds for approval with this code, on both stores. */
function isPaymentPending(mod: PurchasesModule, error: unknown): boolean {
  const code = (error as { code?: unknown } | null)?.code;
  return code === mod.PURCHASES_ERROR_CODE.PAYMENT_PENDING_ERROR;
}

/**
 * Buy the plan for a period; resolves with the plan the store now reports, or "pending" when
 * the store holds the purchase for approval (`heldPurchase.ts`). A subscriber changes period
 * in the store's own subscription page, so nothing here replaces a subscription.
 */
export async function purchasePlanPackage(pkg: PlanPackage): Promise<PlanId | "pending"> {
  const mod = await loadPurchases();
  if (!mod) return "free";
  let result: Awaited<ReturnType<PurchasesModule["default"]["purchasePackage"]>>;
  try {
    result = await mod.default.purchasePackage(pkg.native);
  } catch (error) {
    if (!isPaymentPending(mod, error)) throw error;
    holdPurchase(configuredAppUserId ?? "", pkg.plan);
    return "pending";
  }
  const plan = planFromCustomerInfo(result.customerInfo);
  settleHeldPurchase(plan);
  return plan;
}

/**
 * Restore store purchases; resolves with the plan they grant. A restore also lets go of a
 * held purchase: it is the user's way to check again after a payment that never came.
 */
export async function restorePurchases(): Promise<PlanId> {
  const mod = await loadPurchases();
  if (!mod) return "free";
  const info = await mod.default.restorePurchases();
  await releaseHeldPurchase();
  return planFromCustomerInfo(info);
}

/**
 * L4: log out RevenueCat so the next user doesn't inherit the prior user's
 * entitlements / customer info. No-op when Purchases isn't configured.
 */
export async function signOutRevenueCat(): Promise<void> {
  // The next account waits for its own set-up, and inherits no purchase waiting for approval.
  setupGeneration += 1;
  storeSetUp.set(false);
  await releaseHeldPurchase();
  const mod = await loadPurchases();
  if (!mod) return;
  try {
    await mod.default.logOut();
  } catch {
    // best-effort — local token clear is what matters
  }
  // logOut leaves an anonymous id; the next sign-in logs in by app user id.
  if (configuredAppUserId != null) configuredAppUserId = "";
}

/**
 * Register a listener that fires when the store plan changes (free / pro). RevenueCat calls customerInfoUpdateListener on purchase/restore/expiry
 * and on app foreground; we de-dupe to only invoke `onChange` when the plan
 * actually changes, so callers don't spam a backend sync on every foreground.
 * The listener also fires once on registration with the current state —
 * that's intentional (gives a launch-time sync).
 *
 * Returns a cleanup that removes the listener, or null when Purchases isn't
 * available (Expo Go / web / no API key). */
export async function registerPlanChangeListener(
  onChange: (plan: PlanId) => void,
): Promise<(() => void) | null> {
  const mod = await loadPurchases();
  if (!mod) return null;
  let lastPlan: PlanId | null = null;
  const listener = (info: CustomerInfoLike) => {
    const plan = planFromCustomerInfo(info);
    // An approved Ask to Buy or pending payment arrives here.
    settleHeldPurchase(plan);
    if (plan === lastPlan) return;
    lastPlan = plan;
    onChange(plan);
  };
  mod.default.addCustomerInfoUpdateListener(listener);
  return () => {
    mod.default.removeCustomerInfoUpdateListener(listener);
  };
}
