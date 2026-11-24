import { type ReactNode, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { Pressable, ScrollView, type ScrollViewInstance, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { LinearGradient } from "expo-linear-gradient";
import { useTranslation } from "react-i18next";

import {
  AllBenefits,
  BenefitsLink,
  PlanCard,
  PLANS_FONT_SCALE,
  PlansHairline,
  PlansSmallPrint,
  PlanTimeline,
} from "@/features/billing/components/PlanPicker";
import { heroHeight, PlansHero } from "@/features/billing/components/PlansHero";
import {
  perMonthLine,
  planBenefits,
  priceWithPeriod,
  startTrialText,
  timelineRows,
  yearlySaving,
} from "@/features/billing/model/planCopy";
import { FullScreenModal } from "@/ui/overlay/FullScreenModal";
import { Button } from "@/ui/controls/Button";
import { IconButton } from "@/ui/controls/IconButton";
import { SegmentedControl } from "@/ui/controls/SegmentedControl";
import { useCanRemindTrialEnd, usePlanPurchase } from "@/features/billing/hooks/usePlanPurchase";
import { useStoreOffer } from "@/features/billing/hooks/useStoreOffer";
import { useSubscriptionActions } from "@/features/billing/hooks/useSubscriptionActions";
import { BILLING_PERIODS, type BillingPeriod, type PlanPackage } from "@/features/billing/model/purchases";
import { heldPurchase, subscribeHeldPurchase } from "@/features/billing/model/heldPurchase";
import { DEV_PREVIEW_OFFER } from "@/features/billing/model/devPreviewOffer";
import { BrandAccent } from "@/lib/accentRuntime";
import { type PaidPlanId, planNameKey, planOf, upgradeTargets } from "@/lib/plan";
import { Space } from "@/lib/space";
import { trackProductEvent } from "@/lib/productAnalytics";
import { Theme, useTheme, withAlpha } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import type { Translate } from "@/lib/i18n/translate";

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

/** The plans page: the one paid plan, monthly or yearly, on a full screen in Recall's indigo
 * whatever accent the phone has picked. Kept mounted; `visible` opens it. */
export function UpgradeSheet(props: Props) {
  return (
    <BrandAccent>
      <PlansPage {...props} />
    </BrandAccent>
  );
}

/** Below this height (an iPhone SE, most Android phones with their bars) the headline is a size
 * smaller, so the price and button fit. */
const SHORT_SCREEN = 800;

/** Splits the headline around the plan's name, which is drawn in the accent. */
const PLAN_MARK = "\u2063";

function PlansPage({ visible, onClose, source = "other" }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const { token, user, syncSubscription, devUpgrade, setUpStore } = useSubscriptionActions();
  const current = planOf(user);
  // The one paid plan, or none for an account already on it.
  const plan = upgradeTargets(current)[0] ?? null;
  const { offer, loadingOffer, purchasesReady, retry } = useStoreOffer(visible, setUpStore);
  // A development build has no store: it shows example prices (`devPreviewOffer.ts`).
  const preview = __DEV__ && !purchasesReady;
  const packages = preview ? DEV_PREVIEW_OFFER.packages : offer.packages;
  // A purchase the store holds for approval: said so, and not offered a second time.
  const pending = useSyncExternalStore(subscribeHeldPurchase, heldPurchase);
  const canRemind = useCanRemindTrialEnd(visible);
  const { busy, error, setError, subscribe, restore } = usePlanPurchase({ token, pending, canRemind, syncSubscription, onClose, t });
  const { periods, period, setPicked } = usePeriodChoice(packages);
  const { scroll, benefitsOpen, toggleBenefits } = useBenefitsOpen();
  usePaywallViewed(visible, source, setError);

  // An offer the user did not ask for says Free is a choice, and keeping it is one tap.
  const welcome = (source === "welcome" || source === "nudge") && current === "free";
  const pkg = packages[period];
  const trial = pkg?.trial;
  const shown = plan ?? (current === "free" ? null : current);
  const rows = timelineRows(pkg?.priceString, period, trial, new Date(), t);
  const perMonth = perMonthLine(pkg, t);
  const note = (text: string) => (
    <Text style={s.note} maxFontSizeMultiplier={PLANS_FONT_SCALE}>
      {text}
    </Text>
  );

  return (
    <FullScreenModal visible={visible} animationType="slide" presentationStyle="fullScreen" statusBarTranslucent onRequestClose={onClose} testID="upgrade-page">
      <View style={[s.page, { paddingTop: insets.top, paddingBottom: insets.bottom }]}>
        <PlansWash theme={theme} style={s.wash} />
        <View style={s.topBar}>
          <IconButton name="close" onPress={onClose} accessibilityLabel={t("common.close")} testID="upgrade-close" />
        </View>
        <ScrollView ref={scroll} contentContainerStyle={s.content} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
          {shown ? <PlansHeadline plan={shown} compact={height < SHORT_SCREEN} t={t} styles={s} /> : null}
          {current !== "free" ? note(t("upgrade.current_plan", { plan: t(planNameKey(current)) })) : null}
          <PlansHero height={heroHeight(height)} />
          {plan && periods.length > 1 ? (
            <PeriodSwitch periods={periods} period={period} saving={yearlySaving(packages)} onPick={busy == null ? setPicked : undefined} t={t} />
          ) : null}
          {shown ? (
            <PlanCard title={t("upgrade.plan_title", { plan: t(planNameKey(shown)) })} features={planBenefits(t)} />
          ) : null}
          {plan && rows ? <PlanTimeline rows={rows} /> : null}
          {plan && perMonth ? note(perMonth) : null}
          {plan && trial && canRemind ? note(t("upgrade.trial_reminder")) : null}
          {/* The button is part of the page, under what it costs: nothing scrolls beneath it. */}
          <PlansFooter
            plan={plan}
            period={period}
            pkg={pkg}
            purchasesReady={purchasesReady}
            loading={busy === "buy" || (loadingOffer && !pkg)}
            disabled={pending != null || (purchasesReady && !pkg) || busy === "restore"}
            pending={pending != null}
            error={error}
            benefits={
              shown ? { open: benefitsOpen, label: benefitsLabel(shown, t), onPress: toggleBenefits, features: planBenefits(t) } : null
            }
            legal={
              <PlansSmallPrint
                links={{ terms: t("terms.title"), privacy: t("privacy.title") }}
                restore={purchasesReady ? { label: t("upgrade.restore"), onPress: () => void restore(), disabled: busy != null } : undefined}
              />
            }
            onBuy={() => {
              if (pkg) void subscribe(pkg);
            }}
            onDevEnable={() => {
              if (plan) {
                void devUpgrade(plan).then((ok) => {
                  if (ok) onClose();
                });
              }
            }}
            t={t}
            styles={s}
          />
          {plan ? <StoreNotes unavailable={purchasesReady && offer.unavailable && !loadingOffer} purchasesReady={purchasesReady} onRetry={retry} t={t} styles={s} /> : null}
          {welcome ? <ContinueFree onPress={onClose} disabled={busy != null} t={t} styles={s} /> : null}
        </ScrollView>
      </View>
    </FullScreenModal>
  );
}

/** "See all Pro benefits": the same words open or closed; only its arrow turns. */
function benefitsLabel(plan: PaidPlanId, t: Translate): string {
  return t("upgrade.see_all_benefits", { plan: t(planNameKey(plan)) });
}

/** An offer the user did not ask for keeps Free one tap away. */
function ContinueFree({
  onPress,
  disabled,
  t,
  styles: s,
}: {
  onPress: () => void;
  disabled: boolean;
  t: Translate;
  styles: ReturnType<typeof makeStyles>;
}) {
  return (
    <Pressable onPress={onPress} disabled={disabled} style={s.freeLink} accessibilityRole="button" testID="upgrade-continue-free">
      <Text style={s.freeLinkText}>{t("upgrade.continue_free")}</Text>
    </Pressable>
  );
}

/** The full benefit list, opened under "See all Pro benefits": the page scrolls down to it. */
function useBenefitsOpen() {
  const scroll = useRef<ScrollViewInstance>(null);
  const [benefitsOpen, setBenefitsOpen] = useState(false);
  const toggleBenefits = () => {
    const opening = !benefitsOpen;
    setBenefitsOpen(opening);
    if (opening) setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 50);
  };
  return { scroll, benefitsOpen, toggleBenefits };
}

/** The periods the store sells (both before it has said, so the choice is seen); monthly to
 * start (the owner's choice, 2026-11-24). */
function usePeriodChoice(packages: Partial<Record<BillingPeriod, PlanPackage>>) {
  const sold = BILLING_PERIODS.filter((period) => packages[period]);
  const periods = sold.length > 0 ? sold : BILLING_PERIODS;
  const [picked, setPicked] = useState<BillingPeriod>("monthly");
  return { periods, period: periods.includes(picked) ? picked : periods[0], setPicked };
}

/** Counts each opening of the page once, and clears the last opening's error. */
function usePaywallViewed(visible: boolean, source: UpgradeSource, setError: (error: string | null) => void) {
  const wasVisible = useRef(false);
  useEffect(() => {
    if (visible && !wasVisible.current) {
      trackProductEvent("paywall_viewed", { source });
      setError(null);
    }
    wasVisible.current = visible;
  }, [source, visible, setError]);
}

/** Monthly | Yearly · Save 37%, on the page's tint. Still while a purchase runs. */
function PeriodSwitch({
  periods,
  period,
  saving,
  onPick,
  t,
}: {
  periods: readonly BillingPeriod[];
  period: BillingPeriod;
  saving: number | null;
  onPick: ((period: BillingPeriod) => void) | undefined;
  t: Translate;
}) {
  return (
    <SegmentedControl
      segments={periods.map((key) => ({ key, label: periodLabel(key, saving, t) }))}
      value={period}
      onChange={(next) => onPick?.(next)}
      accessibilityLabel={t("upgrade.billing_period")}
      tinted
      testID="upgrade-period"
    />
  );
}

/** An indigo wash from the top that fades into the page, in the picture's colour. */
function PlansWash({ theme, style }: { theme: Theme; style: object }) {
  const top = withAlpha(theme.primary, theme.isDark ? 0.45 : 0.3);
  const middle = withAlpha(theme.primary, theme.isDark ? 0.12 : 0.08);
  return <LinearGradient colors={[top, middle, theme.bg]} locations={[0, 0.45, 1]} style={style} pointerEvents="none" />;
}

/** What the store could not do: not answering (with Retry), or not in this build at all (a
 * development build then shows example prices, `devPreviewOffer.ts`). Never "Coming soon". */
function StoreNotes({
  unavailable,
  purchasesReady,
  onRetry,
  t,
  styles: s,
}: {
  unavailable: boolean;
  purchasesReady: boolean;
  onRetry: () => void;
  t: Translate;
  styles: ReturnType<typeof makeStyles>;
}) {
  return (
    <>
      {unavailable ? (
        <>
          <Text style={s.error}>{t("upgrade.store_unavailable")}</Text>
          <Button title={t("common.retry")} onPress={onRetry} variant="secondary" />
        </>
      ) : null}
      {/* A release built without its store keys has no button: say why. A development build
          shows its example prices and its own switch instead. */}
      {purchasesReady || __DEV__ ? null : <Text style={s.note}>{t("upgrade.store_not_in_build")}</Text>}
    </>
  );
}

/** The page's action: how the plan renews, the one button, Privacy and Terms, the link to
 * every benefit, and what went wrong. */
function PlansFooter({
  plan,
  period,
  pending,
  error,
  benefits,
  legal,
  styles: s,
  ...buy
}: {
  plan: PaidPlanId | null;
  period: BillingPeriod;
  pkg: PlanPackage | undefined;
  purchasesReady: boolean;
  loading: boolean;
  disabled: boolean;
  pending: boolean;
  error: string | null;
  /** "See all Pro benefits", under the button; none when there is no plan card. */
  benefits: { open: boolean; label: string; onPress: () => void; features: readonly string[] } | null;
  /** Privacy, Terms and Restore, right under the button. */
  legal: ReactNode;
  onBuy: () => void;
  onDevEnable: () => void;
  t: Translate;
  styles: ReturnType<typeof makeStyles>;
}) {
  const { t } = buy;
  return (
    <View style={s.footer}>
      {plan ? (
        <>
          <Text style={s.note} maxFontSizeMultiplier={PLANS_FONT_SCALE}>
            {t(period === "yearly" ? "upgrade.renews_yearly" : "upgrade.renews_monthly")}
          </Text>
          <BuyButton plan={plan} {...buy} />
          {legal}
          {benefits ? (
            <>
              <PlansHairline />
              <BenefitsLink open={benefits.open} label={benefits.label} onPress={benefits.onPress} />
              {benefits.open ? <AllBenefits features={benefits.features} /> : null}
            </>
          ) : null}
          {pending ? (
            <Text style={s.note} testID="upgrade-pending">
              {t("upgrade.purchase_pending")}
            </Text>
          ) : null}
        </>
      ) : (
        // A subscriber still has Privacy, Terms and Restore (a new phone finds the purchase there).
        legal
      )}
      {error ? <Text style={s.error}>{error}</Text> : null}
    </View>
  );
}

/** "Get more with Pro", the plan's name in the accent. */
function PlansHeadline({
  plan,
  compact,
  t,
  styles,
}: {
  plan: PaidPlanId;
  /** A short screen: one size down, so the page fits. */
  compact: boolean;
  t: Translate;
  styles: ReturnType<typeof makeStyles>;
}) {
  const [before, after = ""] = t("upgrade.headline", { plan: PLAN_MARK }).split(PLAN_MARK);
  return (
    <Text style={[styles.headline, compact && styles.headlineCompact]} accessibilityRole="header" maxFontSizeMultiplier={PLANS_FONT_SCALE}>
      {before}
      <Text style={styles.headlinePlan}>{t(planNameKey(plan))}</Text>
      {after}
    </Text>
  );
}

/** "Yearly · Save 37%" when the year costs less than twelve months; else the period's name. */
function periodLabel(period: BillingPeriod, saving: number | null, t: Translate): string {
  if (period === "monthly") return t("upgrade.period_monthly");
  return saving ? t("upgrade.period_yearly_save", { percent: saving }) : t("upgrade.period_yearly");
}

/** Buys the plan for the picked period. A build with no store keys cannot sell: in
 * development it switches the plan without paying (the server's dev upgrade), and in a
 * release it says the store is missing (above). */
function BuyButton({
  plan,
  pkg,
  purchasesReady,
  loading,
  disabled,
  onBuy,
  onDevEnable,
  t,
}: {
  plan: PaidPlanId;
  /** The picked period's package, once the store has said it: its price, and its trial. */
  pkg: PlanPackage | undefined;
  purchasesReady: boolean;
  loading: boolean;
  disabled: boolean;
  onBuy: () => void;
  onDevEnable: () => void;
  t: Translate;
}) {
  const name = t(planNameKey(plan));
  const price = pkg ? priceWithPeriod(pkg, t) : undefined;
  if (!purchasesReady) {
    return __DEV__ ? (
      <Button title={t("upgrade.dev_enable_plan", { plan: name })} onPress={onDevEnable} size="lg" style={BUY_STYLE} />
    ) : null;
  }
  return (
    <Button
      title={
        pkg?.trial
          ? startTrialText(pkg.trial, t)
          : price
            ? t("upgrade.subscribe_price", { plan: name, price })
            : t("upgrade.subscribe_plan", { plan: name })
      }
      onPress={onBuy}
      loading={loading}
      disabled={disabled}
      size="lg"
      style={BUY_STYLE}
      testID="upgrade-subscribe"
    />
  );
}

/** The buy button, a step taller than a large button: the page's one action. */
const BUY_STYLE = { minHeight: 58 };

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    page: { flex: 1, backgroundColor: theme.bg },
    wash: { position: "absolute", top: 0, left: 0, right: 0, height: "70%" },
    topBar: { flexDirection: "row", paddingHorizontal: Space.sm },
    content: { flexGrow: 1, paddingHorizontal: Space.gutter, paddingBottom: Space.md, gap: Space.sm },
    headline: { ...Type.greeting, ...Weight.bold, textAlign: "center", color: theme.text },
    headlinePlan: { color: theme.primary },
    headlineCompact: { ...Type.display },
    footer: { gap: Space.xs },
    freeLink: { alignSelf: "center", paddingVertical: Space.xs, paddingHorizontal: Space.md },
    freeLinkText: { ...Type.body, ...Weight.semibold, color: theme.textSecondary },
    error: { ...Type.secondary, color: theme.danger, textAlign: "center" },
    note: { ...Type.secondary, color: theme.textSecondary, textAlign: "center" },
  });
