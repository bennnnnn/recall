import { useAccountSession } from "@/contexts/accountSession";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Pressable, StyleSheet, Text } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useTranslation } from "react-i18next";

import {
  type FeatureLine,
  PlanBenefits,
  PlansSmallPrint,
  PlanTiles,
  type Tile,
} from "@/features/billing/components/PlanPicker";
import { Sheet } from "@/ui/overlay/Sheet";
import { Button } from "@/ui/controls/Button";
import { useSubscriptionActions } from "@/features/billing/hooks/useSubscriptionActions";
import { api } from "@/lib/api";
import { reportFailure } from "@/lib/sentry";
import {
  getPlanPackages,
  isPurchaseCancelled,
  isPurchasesConfigured,
  isStoreReady,
  type PlanOffer,
  purchasePlanPackage,
  recheckPendingPurchase,
  restorePurchases,
  subscribeStoreReady,
} from "@/features/billing/model/purchases";
import { heldPurchase, subscribeHeldPurchase } from "@/features/billing/model/heldPurchase";
import { onAppStateChange } from "@/lib/foregroundRefresh";
import {
  type PaidPlanId,
  PLAN_RANK,
  type PlanCatalog,
  type PlanId,
  type PlanInfo,
  planNameKey,
  planOf,
  upgradeTargets,
} from "@/lib/plan";
import { Space } from "@/lib/space";
import { trackProductEvent } from "@/lib/productAnalytics";
import { Theme, useTheme, withAlpha } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Radius } from "@/lib/radius";

/** Where the sheet was opened from: "welcome" is the offer after the first sign-in, "nudge"
 * the one now and then after it (`welcomePlans`). */
export type UpgradeSource =
  | "quota"
  | "model_gate"
  | "settings"
  | "voice"
  | "live_talk"
  | "welcome"
  | "nudge"
  | "other";

type Props = {
  visible: boolean;
  onClose: () => void;
  source?: UpgradeSource;
};

type Translate = (key: string, options?: Record<string, unknown>) => string;

const NO_OFFER: PlanOffer = { packages: {}, unavailable: false };
const STORE_NOT_SET_UP: PlanOffer = { packages: {}, unavailable: true };
/** How long the sheet waits for the store's set-up before saying the store is not answering. */
const STORE_SETUP_WAIT_MS = 8_000;
/** "200 messages a day": what a plan offers, never which model answers. */
function messagesLine(info: PlanInfo | undefined, t: Translate): FeatureLine {
  const count = info?.allowances.daily_messages;
  return { icon: "message", text: count ? t("upgrade.feature_messages", { count }) : t("upgrade.feature_messages_plain") };
}

/** What a plan gives, in what the user gets, with the server's numbers (the store owns the
 * price); the messages line says what Free has beside it. */
function planFeatureLines(
  plan: PaidPlanId,
  catalog: PlanCatalog | null,
  t: Translate,
): FeatureLine[] {
  const info = catalog?.plans.find((item) => item.id === plan);
  const free = catalog?.plans.find((item) => item.id === "free")?.allowances.daily_messages;
  const lines: FeatureLine[] = [
    { ...messagesLine(info, t), note: free ? t("upgrade.free_has", { count: free }) : undefined },
  ];
  const images = info?.allowances.daily_image_generations;
  if (plan === "pro") {
    const minutes = info?.allowances.monthly_live_talk_minutes;
    lines.push({
      icon: "activity",
      text: minutes ? t("upgrade.feature_live_talk", { count: minutes }) : t("upgrade.feature_live_talk_plain"),
    });
    lines.push({ icon: "sparkles", text: t("upgrade.feature_sharper") });
  } else {
    lines.push({ icon: "mic", text: t("upgrade.feature_voice") });
  }
  if (images) lines.push({ icon: "image", text: t("upgrade.feature_images", { count: images }) });
  if (plan === "pro") lines.push({ icon: "check", text: t("upgrade.everything_in", { plan: t(planNameKey("plus")) }) });
  return lines;
}

/**
 * The store's plans while the sheet shows. RevenueCat answers nothing before it is set up
 * for this account (after the server confirms the account and its plan), so the read waits
 * for that, the button spinning. A launch that never reached the server, or a set-up that
 * hung, leaves it waiting: after `STORE_SETUP_WAIT_MS` the store is said to be unavailable,
 * and Retry sets it up again (`setUpStore`).
 */
function useStoreOffer(visible: boolean, setUpStore: () => Promise<void>) {
  const purchasesReady = isPurchasesConfigured();
  const storeReady = useSyncExternalStore(subscribeStoreReady, isStoreReady);
  const [offer, setOffer] = useState<PlanOffer>(NO_OFFER);
  const [attempt, setAttempt] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!visible || !purchasesReady) {
      setOffer(NO_OFFER);
      return;
    }
    setLoading(true);
    if (!storeReady) {
      const late = setTimeout(() => {
        setOffer(STORE_NOT_SET_UP);
        setLoading(false);
      }, STORE_SETUP_WAIT_MS);
      return () => clearTimeout(late);
    }
    let cancelled = false;
    void getPlanPackages()
      .then((next) => {
        if (!cancelled) setOffer(next);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [visible, purchasesReady, storeReady, attempt]);

  // A held purchase is read again as the sheet opens and as the app comes back.
  useEffect(() => {
    if (!visible) return;
    void recheckPendingPurchase();
    return onAppStateChange((_state, returned) => {
      if (returned) void recheckPendingPurchase();
    });
  }, [visible]);

  const retry = useCallback(() => {
    if (!isStoreReady()) {
      void setUpStore().catch((error: unknown) => reportFailure("paywall_load", error));
    }
    setAttempt((count) => count + 1);
  }, [setUpStore]);
  return { offer, loadingOffer: loading, purchasesReady, retry };
}

export function UpgradeSheet({ visible, onClose, source = "other" }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = makeStyles(theme);
  const { token, user, syncSubscription, devUpgrade, setUpStore } = useSubscriptionActions();
  const { account, getToken } = useAccountSession();
  const current = planOf(user);
  const targets = upgradeTargets(current);
  const { offer, loadingOffer, purchasesReady, retry } = useStoreOffer(visible, setUpStore);
  const packages = offer.packages;
  // A purchase the store holds for approval: said so, and not offered a second time.
  const pending = useSyncExternalStore(subscribeHeldPurchase, heldPurchase);
  const [catalog, setCatalog] = useState<PlanCatalog | null>(null);
  const [busy, setBusy] = useState<PaidPlanId | "restore" | null>(null);
  const [error, setError] = useState<string | null>(null);
  // The plan the one button buys: the first one up from the current plan to start.
  const [picked, setPicked] = useState<PaidPlanId | null>(null);
  const chosen = picked && targets.includes(picked) ? picked : (targets[0] ?? null);
  const wasVisible = useRef(false);

  useEffect(() => {
    if (visible && !wasVisible.current) {
      trackProductEvent("paywall_viewed", { source });
      setError(null);
    }
    wasVisible.current = visible;
  }, [source, visible]);

  useEffect(() => {
    const token = getToken();
    if (!visible || !account || !token) return;
    let cancelled = false;
    void api
      .listPlans(token)
      .then((next) => {
        if (!cancelled) setCatalog(next);
      })
      // The cards still show what each plan includes, without numbers.
      .catch((error: unknown) => reportFailure("paywall_load", error));
    return () => {
      cancelled = true;
    };
  }, [visible, account, getToken]);

  /** The server reads the store again. The store took the payment, so a failure here says
   * "pending", never that it failed: the plan listener and the webhook still land it. */
  const syncAfterStore = async () => {
    if (!token) return;
    try {
      await syncSubscription();
      onClose();
    } catch (error) {
      reportFailure("purchase_sync", error);
      setError(t("upgrade.sync_pending"));
    }
  };

  const onSubscribe = async (plan: PaidPlanId) => {
    const pkg = packages[plan];
    if (!token || !pkg || busy || pending) return;
    setBusy(plan);
    setError(null);
    trackProductEvent("purchase_started", { plan });
    let purchased: PlanId | "pending" = "free";
    try {
      purchased = await purchasePlanPackage(pkg);
    } catch (purchaseError) {
      const cancelled = isPurchaseCancelled(purchaseError);
      trackProductEvent("purchase_failed", {
        plan,
        reason: cancelled ? "cancelled" : "error",
      });
      if (!cancelled) reportFailure("purchase", purchaseError);
      if (!cancelled) setError(t("upgrade.purchase_failed"));
      setBusy(null);
      return;
    }
    // Neither bought nor failed: the store waits for approval, and the plan listener lands it.
    if (purchased === "pending") {
      setBusy(null);
      return;
    }
    if (PLAN_RANK[purchased] < PLAN_RANK[plan]) {
      trackProductEvent("purchase_failed", { plan, reason: "error" });
      setError(t("upgrade.purchase_failed"));
      setBusy(null);
      return;
    }
    trackProductEvent("purchase_succeeded", { plan });
    await syncAfterStore();
    setBusy(null);
  };

  const onRestore = async () => {
    if (!token || busy) return;
    setBusy("restore");
    setError(null);
    try {
      const restored = await restorePurchases();
      if (restored === "free") {
        setError(t("upgrade.restore_empty"));
        return;
      }
      await syncAfterStore();
    } catch (error) {
      reportFailure("purchase_restore", error);
      setError(t("upgrade.purchase_failed"));
    } finally {
      setBusy(null);
    }
  };

  // An offer the user did not ask for says Free is a choice, and keeping it is one tap.
  const welcome = (source === "welcome" || source === "nudge") && current === "free";

  return (
    <Sheet
      visible={visible}
      onClose={onClose}
      minBottomPadding={36}
      contentContainerStyle={s.sheet}
    >
      <LinearGradient colors={[theme.primary, theme.primaryDark]} style={s.hero}>
        <Text style={s.heroTitle} accessibilityRole="header">{t(welcome ? "upgrade.welcome_title" : "upgrade.title")}</Text>
        <Text style={s.heroBody}>
          {current !== "free" ? t("upgrade.current_plan", { plan: t(planNameKey(current)) }) : t("upgrade.cancel_anytime")}
        </Text>
      </LinearGradient>
      <PlanTiles tiles={planTiles(targets, catalog, packages, t)} picked={chosen} onPick={(id) => setPicked(id as PaidPlanId)} disabled={busy != null} />
      {chosen ? (
        <PlanBenefits heading={t("upgrade.benefits_heading", { plan: t(planNameKey(chosen)) })} lines={planFeatureLines(chosen, catalog, t)} />
      ) : null}
      {chosen ? (
        <BuyButton
          plan={chosen}
          price={packages[chosen]?.priceString}
          purchasesReady={purchasesReady}
          loading={busy === chosen || (loadingOffer && !packages[chosen])}
          disabled={pending != null || (purchasesReady && !packages[chosen]) || (busy != null && busy !== chosen)}
          onBuy={() => void onSubscribe(chosen)}
          onDevEnable={() => {
            void devUpgrade(chosen).then((ok) => {
              if (ok) onClose();
            });
          }}
          style={s.primaryBtn}
          t={t}
        />
      ) : null}
      {purchasesReady && offer.unavailable && !loadingOffer ? (
        <>
          <Text style={s.error}>{t("upgrade.store_unavailable")}</Text>
          <Button
            title={t("common.retry")}
            onPress={retry}
            variant="secondary"
            style={s.primaryBtn}
          />
        </>
      ) : null}
      {pending ? <Text style={s.note} testID="upgrade-pending">{t("upgrade.purchase_pending")}</Text> : null}
      {error ? <Text style={s.error}>{error}</Text> : null}
      {welcome ? (
        <Pressable onPress={onClose} disabled={busy != null} style={s.freeLink} accessibilityRole="button" testID="upgrade-continue-free">
          <Text style={s.freeLinkText}>{t("upgrade.continue_free")}</Text>
        </Pressable>
      ) : null}
      {/* A build with no store keys (Expo Go, a local build) cannot sell: say so, never "Coming soon". */}
      {purchasesReady ? null : <Text style={s.note}>{t("upgrade.store_not_in_build")}</Text>}
      <PlansSmallPrint
        renews={t("upgrade.subscription_terms")}
        links={{ terms: t("terms.title"), privacy: t("privacy.title") }}
        restore={purchasesReady ? { label: t("upgrade.restore"), onPress: () => void onRestore(), disabled: busy != null } : undefined}
      />
    </Sheet>
  );
}

/** The paid plans as tiles: the store's price when it has said one, and the day's messages. */
function planTiles(
  targets: readonly PaidPlanId[],
  catalog: PlanCatalog | null,
  packages: PlanOffer["packages"],
  t: Translate,
): Tile[] {
  return targets.map((plan) => ({
    id: plan,
    name: t(planNameKey(plan)),
    price: packages[plan]?.priceString,
    perMonth: t("upgrade.per_month_suffix"),
    headline: messagesLine(
      catalog?.plans.find((item) => item.id === plan),
      t,
    ).text,
  }));
}

/** Buys the picked plan. A build with no store keys cannot sell: in development it
 * switches the plan without paying (the server's dev upgrade), and in a release it says
 * the store is missing (below). */
function BuyButton({
  plan,
  price,
  purchasesReady,
  loading,
  disabled,
  onBuy,
  onDevEnable,
  style,
  t,
}: {
  plan: PaidPlanId;
  price: string | undefined;
  purchasesReady: boolean;
  loading: boolean;
  disabled: boolean;
  onBuy: () => void;
  onDevEnable: () => void;
  style: object;
  t: Translate;
}) {
  const name = t(planNameKey(plan));
  if (!purchasesReady) {
    return __DEV__ ? (
      <Button title={t("upgrade.dev_enable_plan", { plan: name })} onPress={onDevEnable} size="lg" style={style} />
    ) : null;
  }
  return (
    <Button
      title={price ? t("upgrade.subscribe_for", { plan: name, price }) : t("upgrade.subscribe_plan", { plan: name })}
      onPress={onBuy}
      loading={loading}
      disabled={disabled}
      size="lg"
      style={style}
      testID="upgrade-subscribe"
    />
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    sheet: {
      backgroundColor: theme.bg,
      paddingHorizontal: Space.gutter,
      paddingTop: Space.md,
      gap: Space.md,
    },
    hero: { borderRadius: Radius.xl, paddingHorizontal: Space.gutter, paddingVertical: Space.lg, gap: Space.xxs },
    heroTitle: { ...Type.h1, color: theme.onPrimary },
    heroBody: { ...Type.body, color: withAlpha(theme.onPrimary, 0.85) },
    freeLink: { alignSelf: "center", paddingVertical: Space.xs, paddingHorizontal: Space.md },
    freeLinkText: { ...Type.body, ...Weight.semibold, color: theme.textSecondary },
    error: {
      ...Type.secondary,
      color: theme.danger,
      textAlign: "center",
    },
    primaryBtn: {
      marginTop: Space.xxs,
    },
    note: {
      ...Type.secondary,
      color: theme.textSecondary,
      textAlign: "center",
    },
  });
