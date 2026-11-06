import { useAccountSession } from "@/contexts/accountSession";
import { useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import { type FeatureLine, PlanCard } from "@/features/billing/components/PlanCard";
import { Sheet } from "@/ui/overlay/Sheet";
import { Button } from "@/ui/controls/Button";
import { useSubscriptionActions } from "@/features/billing/hooks/useSubscriptionActions";
import { api } from "@/lib/api";
import { reportFailure } from "@/lib/sentry";
import {
  getPlanPackages,
  isPurchaseCancelled,
  isPurchasesConfigured,
  type PlanOffer,
  purchasePlanPackage,
  restorePurchases,
} from "@/features/billing/model/purchases";
import {
  type PaidPlanId,
  type PlanCatalog,
  type PlanId,
  type PlanInfo,
  planNameKey,
  planOf,
  upgradeTargets,
} from "@/lib/plan";
import { Space } from "@/lib/space";
import { trackProductEvent } from "@/lib/productAnalytics";
import { getLegalPrivacyUrl, getLegalTermsUrl } from "@/lib/legalUrls";
import { openAllowedUrl } from "@/lib/linkSchemePolicy";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { IconSize } from "@/ui/icons/sizes";
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

const PLAN_RANK: Record<PlanId, number> = { free: 0, plus: 1, pro: 2 };

const NO_OFFER: PlanOffer = { packages: {}, unavailable: false };
/** A 12pt link line is about 17pt tall: this makes it a 45pt target, short of the next link. */
const LEGAL_LINK_SLOP = { top: 14, bottom: 14, left: Space.xs, right: Space.xs };

/** What Free already gives, so the plans above it read as more of something known. */
function freeIncludes(catalog: PlanCatalog | null, t: Translate): string {
  const count = catalog?.plans.find((item) => item.id === "free")?.allowances.daily_messages;
  return count ? t("upgrade.free_includes", { count }) : t("upgrade.free_includes_plain");
}

/** "200 messages a day": what a plan offers, never which model answers. */
function messagesLine(info: PlanInfo | undefined, t: Translate): FeatureLine {
  const count = info?.allowances.daily_messages;
  return { icon: "message", text: count ? t("upgrade.feature_messages", { count }) : t("upgrade.feature_messages_plain") };
}

/** What a plan gives, in what the user gets, with the server's numbers (the store owns the price). */
function planFeatureLines(plan: PaidPlanId, info: PlanInfo | undefined, t: Translate): FeatureLine[] {
  const lines: FeatureLine[] = [messagesLine(info, t)];
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

export function UpgradeSheet({ visible, onClose, source = "other" }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = makeStyles(theme);
  const { token, user, syncSubscription, devUpgrade } = useSubscriptionActions();
  const { account, getToken } = useAccountSession();
  const current = planOf(user);
  const targets = upgradeTargets(current);
  const [offer, setOffer] = useState<PlanOffer>(NO_OFFER);
  const [offerAttempt, setOfferAttempt] = useState(0);
  const packages = offer.packages;
  const [catalog, setCatalog] = useState<PlanCatalog | null>(null);
  const [loadingOffer, setLoadingOffer] = useState(false);
  const [busy, setBusy] = useState<PaidPlanId | "restore" | null>(null);
  const [error, setError] = useState<string | null>(null);
  // The plan the one button buys: the first one up from the current plan to start.
  const [picked, setPicked] = useState<PaidPlanId | null>(null);
  const chosen = picked && targets.includes(picked) ? picked : (targets[0] ?? null);
  const purchasesReady = isPurchasesConfigured();
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

  useEffect(() => {
    if (!visible || !purchasesReady) {
      setOffer(NO_OFFER);
      return;
    }
    let cancelled = false;
    setLoadingOffer(true);
    void getPlanPackages()
      .then((next) => {
        if (!cancelled) setOffer(next);
      })
      .finally(() => {
        if (!cancelled) setLoadingOffer(false);
      });
    return () => {
      cancelled = true;
    };
  }, [visible, purchasesReady, offerAttempt]);

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
    if (!token || !pkg || busy) return;
    setBusy(plan);
    setError(null);
    trackProductEvent("purchase_started", { plan });
    let purchased: PlanId = "free";
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

  const planInfo = (plan: PaidPlanId) => catalog?.plans.find((item) => item.id === plan);
  // An offer the user did not ask for says Free is a choice, and keeping it is one tap.
  const welcome = (source === "welcome" || source === "nudge") && current === "free";

  return (
    <Sheet
      visible={visible}
      onClose={onClose}
      minBottomPadding={36}
      contentContainerStyle={s.sheet}
    >
      <View style={s.iconWrap}>
        <Icon name="sparkles" size={IconSize.lg} color={theme.primary} />
      </View>
      <Text style={s.title} accessibilityRole="header">{t(welcome ? "upgrade.welcome_title" : "upgrade.title")}</Text>
      {current !== "free" ? (
        <Text style={s.body}>{t("upgrade.current_plan", { plan: t(planNameKey(current)) })}</Text>
      ) : (
        <Text style={s.body}>{t(welcome ? "upgrade.welcome_body" : "upgrade.body")}</Text>
      )}
      {current === "free" ? <Text style={s.freeLine}>{freeIncludes(catalog, t)}</Text> : null}
      {targets.map((plan) => (
        <PlanCard
          key={plan}
          name={t(planNameKey(plan))}
          price={priceLabel(packages[plan]?.priceString, t)}
          lines={planFeatureLines(plan, planInfo(plan), t)}
          picked={plan === chosen}
          onPick={() => setPicked(plan)}
          disabled={busy != null}
          testID={`upgrade-plan-${plan}`}
        />
      ))}
      {chosen ? (
        <BuyButton
          plan={chosen}
          price={packages[chosen]?.priceString}
          purchasesReady={purchasesReady}
          loading={busy === chosen || (loadingOffer && !packages[chosen])}
          disabled={(purchasesReady && !packages[chosen]) || (busy != null && busy !== chosen)}
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
            onPress={() => setOfferAttempt((attempt) => attempt + 1)}
            variant="secondary"
            style={s.primaryBtn}
          />
        </>
      ) : null}
      {error ? <Text style={s.error}>{error}</Text> : null}
      {welcome ? (
        <Button
          title={t("upgrade.continue_free")}
          onPress={onClose}
          variant="secondary"
          disabled={busy != null}
          style={s.primaryBtn}
          testID="upgrade-continue-free"
        />
      ) : null}
      {purchasesReady ? (
        <Button
          title={t("upgrade.restore")}
          onPress={() => void onRestore()}
          variant="ghost"
          loading={busy === "restore"}
          disabled={busy != null && busy !== "restore"}
        />
      ) : (
        // A build with no store keys (Expo Go, a local build) cannot sell: say so, never "Coming soon".
        <Text style={s.storeMissing}>{t("upgrade.store_not_in_build")}</Text>
      )}
      <Text style={s.subscriptionTerms}>{t("upgrade.subscription_terms")}</Text>
      <View style={s.legalLinks}>
        <Pressable
          onPress={() => void openAllowedUrl(getLegalTermsUrl())}
          accessibilityRole="link"
          accessibilityLabel={t("terms.title")}
          hitSlop={LEGAL_LINK_SLOP}
        >
          <Text style={s.legalLink}>{t("terms.title")}</Text>
        </Pressable>
        <Text style={s.legalSeparator} accessibilityElementsHidden importantForAccessibility="no">·</Text>
        <Pressable
          onPress={() => void openAllowedUrl(getLegalPrivacyUrl())}
          accessibilityRole="link"
          accessibilityLabel={t("privacy.title")}
          hitSlop={LEGAL_LINK_SLOP}
        >
          <Text style={s.legalLink}>{t("privacy.title")}</Text>
        </Pressable>
      </View>
    </Sheet>
  );
}

/** "$7.99/month", or a pointer to the store when the store has not said. */
function priceLabel(price: string | undefined, t: Translate): string {
  return price ? t("upgrade.per_month", { price }) : t("upgrade.price_fallback");
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
      paddingHorizontal: Space.lg,
      paddingTop: Space.lg,
      gap: Space.sm,
    },
    iconWrap: {
      width: 52,
      height: 52,
      borderRadius: Radius.full,
      backgroundColor: theme.primaryLight,
      alignItems: "center",
      justifyContent: "center",
      alignSelf: "center",
    },
    title: {
      ...Type.h1,
      color: theme.text,
      textAlign: "center",
    },
    body: {
      ...Type.secondary,
      color: theme.textSecondary,
      textAlign: "center",
    },
    freeLine: {
      ...Type.caption,
      ...Weight.semibold,
      color: theme.textSecondary,
      textAlign: "center",
    },
    error: {
      ...Type.secondary,
      color: theme.danger,
      textAlign: "center",
    },
    primaryBtn: {
      marginTop: Space.xxs,
    },
    storeMissing: {
      ...Type.secondary,
      color: theme.textSecondary,
      textAlign: "center",
    },
    subscriptionTerms: {
      ...Type.caption,
      color: theme.textTertiary,
      textAlign: "center",
      lineHeight: 17,
    },
    legalLinks: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: Space.xs,
    },
    legalLink: {
      ...Type.caption,
      color: theme.primary,
      ...Weight.semibold,
    },
    legalSeparator: {
      ...Type.caption,
      color: theme.textTertiary,
    },
  });
