import { Platform } from "react-native";

import { isExpoGo } from "@/lib/expoRuntime";

const ENTITLEMENT_ID = "pro";

/** Opaque handle — keeps react-native-purchases out of the static import graph. */
export type ProPurchasePackage = {
  priceString: string;
  native: unknown;
};

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
  if (Platform.OS === "web" || isExpoGo()) return false;
  return revenueCatApiKey() != null;
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
  } catch {
    purchasesModule = null;
    return null;
  }
}

export async function configurePurchases(appUserId: string): Promise<void> {
  const mod = await loadPurchases();
  const apiKey = revenueCatApiKey();
  if (!mod || !apiKey) return;
  mod.default.setLogLevel(__DEV__ ? mod.LOG_LEVEL.DEBUG : mod.LOG_LEVEL.WARN);
  await mod.default.configure({ apiKey, appUserID: appUserId });
}

export async function getMonthlyProPackage(): Promise<ProPurchasePackage | null> {
  const mod = await loadPurchases();
  if (!mod) return null;
  try {
    const offerings = await mod.default.getOfferings();
    const offering = offerings.current;
    if (!offering) return null;
    const pkg =
      offering.monthly ??
      offering.availablePackages.find((item) => item.packageType === "MONTHLY") ??
      offering.availablePackages[0] ??
      null;
    if (!pkg) return null;
    return { priceString: pkg.product.priceString, native: pkg };
  } catch {
    return null;
  }
}

export async function purchaseProPackage(pkg: ProPurchasePackage): Promise<boolean> {
  const mod = await loadPurchases();
  if (!mod) return false;
  const result = await mod.default.purchasePackage(pkg.native as never);
  return result.customerInfo.entitlements.active[ENTITLEMENT_ID] != null;
}

export async function restorePurchases(): Promise<boolean> {
  const mod = await loadPurchases();
  if (!mod) return false;
  const info = await mod.default.restorePurchases();
  return info.entitlements.active[ENTITLEMENT_ID] != null;
}

export async function hasActiveProEntitlement(): Promise<boolean> {
  const mod = await loadPurchases();
  if (!mod) return false;
  try {
    const info = await mod.default.getCustomerInfo();
    return info.entitlements.active[ENTITLEMENT_ID] != null;
  } catch {
    return false;
  }
}

/**
 * Register a listener that fires when the Pro entitlement state changes.
 * RevenueCat calls customerInfoUpdateListener on purchase/restore/expiry and
 * on app foreground; we de-dupe to only invoke `onChange` when the active
 * state actually flips, so callers don't spam a backend sync on every
 * foreground. The listener also fires once on registration with the current
 * state — that's intentional (gives a launch-time sync).
 *
 * Returns a cleanup that removes the listener, or null when Purchases isn't
 * available (Expo Go / web / no API key). */
export async function registerPlanChangeListener(
  onChange: (isPro: boolean) => void,
): Promise<(() => void) | null> {
  const mod = await loadPurchases();
  if (!mod) return null;
  let lastActive: boolean | null = null;
  const listener = (info: {
    entitlements: { active: Record<string, unknown> };
  }) => {
    const active = info.entitlements.active[ENTITLEMENT_ID] != null;
    if (active === lastActive) return;
    lastActive = active;
    onChange(active);
  };
  mod.default.addCustomerInfoUpdateListener(listener);
  return () => {
    mod.default.removeCustomerInfoUpdateListener(listener);
  };
}
