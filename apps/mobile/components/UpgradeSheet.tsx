import { useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { AppSheet } from "@/components/AppSheet";
import { Button } from "@/components/Button";
import { useSubscriptionActions } from "@/hooks/useSubscriptionActions";
import { type IoniconName } from "@/lib/icons";
import {
  getMonthlyProPackage,
  isPurchaseCancelled,
  isPurchasesConfigured,
  type ProPurchasePackage,
  purchaseProPackage,
  restorePurchases,
} from "@/lib/purchases";
import { Space } from "@/lib/space";
import { trackProductEvent } from "@/lib/productAnalytics";
import { getLegalPrivacyUrl, getLegalTermsUrl } from "@/lib/legalUrls";
import { openAllowedUrl } from "@/lib/linkSchemePolicy";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  visible: boolean;
  onClose: () => void;
  source?: "quota" | "model_gate" | "settings" | "other";
};

export function UpgradeSheet({ visible, onClose, source = "other" }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = makeStyles(theme);
  const { token, syncSubscription, devUpgrade } = useSubscriptionActions();
  const [pkg, setPkg] = useState<ProPurchasePackage | null>(null);
  const [loadingOffer, setLoadingOffer] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const purchasesReady = isPurchasesConfigured();
  const wasVisible = useRef(false);

  useEffect(() => {
    if (visible && !wasVisible.current) {
      trackProductEvent(token, "paywall_viewed", { source });
    }
    wasVisible.current = visible;
  }, [source, token, visible]);

  useEffect(() => {
    if (!visible || !purchasesReady) {
      setPkg(null);
      return;
    }
    let cancelled = false;
    setLoadingOffer(true);
    void getMonthlyProPackage()
      .then((next) => {
        if (!cancelled) setPkg(next);
      })
      .finally(() => {
        if (!cancelled) setLoadingOffer(false);
      });
    return () => {
      cancelled = true;
    };
  }, [visible, purchasesReady]);

  const syncAfterStore = async () => {
    if (!token) return;
    await syncSubscription();
    onClose();
  };

  const tryDevUpgrade = async () => {
    if (!token) return;
    try {
      if (await devUpgrade()) onClose();
    } catch {
      /* dev endpoint unavailable in production */
    }
  };

  const onSubscribe = async () => {
    if (!token || !pkg || busy) return;
    setBusy(true);
    setError(null);
    trackProductEvent(token, "purchase_started");
    let purchased = false;
    try {
      purchased = await purchaseProPackage(pkg);
    } catch (purchaseError) {
      const cancelled = isPurchaseCancelled(purchaseError);
      trackProductEvent(token, "purchase_failed", {
        reason: cancelled ? "cancelled" : "error",
      });
      if (!cancelled) setError(t("upgrade.purchase_failed"));
      setBusy(false);
      return;
    }
    if (!purchased) {
      trackProductEvent(token, "purchase_failed", { reason: "error" });
      setError(t("upgrade.purchase_failed"));
      setBusy(false);
      return;
    }
    trackProductEvent(token, "purchase_succeeded");
    try {
      await syncAfterStore();
    } catch {
      // The store purchase succeeded; subscription bootstrap can retry without
      // corrupting the purchase funnel with a false provider failure.
      setError(t("upgrade.purchase_failed"));
    } finally {
      setBusy(false);
    }
  };

  const onRestore = async () => {
    if (!token || busy) return;
    setBusy(true);
    setError(null);
    try {
      const ok = await restorePurchases();
      if (!ok) {
        setError(t("upgrade.restore_empty"));
        return;
      }
      await syncAfterStore();
    } catch {
      setError(t("upgrade.purchase_failed"));
    } finally {
      setBusy(false);
    }
  };

  const priceLabel = pkg?.priceString ?? t("upgrade.price_fallback");

  return (
    <AppSheet
      visible={visible}
      onClose={onClose}
      minBottomPadding={36}
      contentContainerStyle={s.sheet}
    >
      <View style={s.iconWrap}>
        <Icon name="sparkles" size={28} color={theme.primary} />
      </View>
      <Text style={s.title}>{t("upgrade.title")}</Text>
      <Text style={s.body}>{t("upgrade.body")}</Text>
      <View style={s.featureList}>
        <FeatureRow icon="flash-outline" text={t("upgrade.feature_models")} theme={theme} />
        <FeatureRow icon="infinite-outline" text={t("upgrade.feature_limits")} theme={theme} />
        <FeatureRow icon="options-outline" text={t("upgrade.feature_pick")} theme={theme} />
      </View>
      {error ? <Text style={s.error}>{error}</Text> : null}
      {purchasesReady ? (
        <>
          <Button
            title={t("upgrade.subscribe", { price: priceLabel })}
            onPress={() => void onSubscribe()}
            loading={busy || loadingOffer}
            disabled={!pkg}
            style={s.primaryBtn}
          />
          <Button
            title={t("upgrade.restore")}
            onPress={() => void onRestore()}
            variant="ghost"
            disabled={busy}
          />
        </>
      ) : (
        <Button title={t("upgrade.coming_soon")} onPress={onClose} style={s.primaryBtn} />
      )}
      <Text style={s.subscriptionTerms}>{t("upgrade.subscription_terms")}</Text>
      <View style={s.legalLinks}>
        <Pressable
          onPress={() => void openAllowedUrl(getLegalTermsUrl())}
          accessibilityRole="link"
          accessibilityLabel={t("terms.title")}
        >
          <Text style={s.legalLink}>{t("terms.title")}</Text>
        </Pressable>
        <Text style={s.legalSeparator}>·</Text>
        <Pressable
          onPress={() => void openAllowedUrl(getLegalPrivacyUrl())}
          accessibilityRole="link"
          accessibilityLabel={t("privacy.title")}
        >
          <Text style={s.legalLink}>{t("privacy.title")}</Text>
        </Pressable>
      </View>
      {__DEV__ ? (
        <Pressable style={s.devBtn} onPress={() => void tryDevUpgrade()}>
          <Text style={s.devBtnText}>{t("upgrade.dev_enable")}</Text>
        </Pressable>
      ) : null}
    </AppSheet>
  );
}

function FeatureRow({
  icon,
  text,
  theme,
}: {
  icon: IoniconName;
  text: string;
  theme: Theme;
}) {
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: Space.xs }}>
      <Icon name={icon} size={18} color={theme.primary} />
      <Text style={{ flex: 1, ...Type.secondary, color: theme.textSecondary }}>{text}</Text>
    </View>
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
      borderRadius: 26,
      backgroundColor: theme.primaryLight,
      alignItems: "center",
      justifyContent: "center",
      alignSelf: "center",
    },
    title: {
      fontSize: 22,
      fontWeight: "700",
      color: theme.text,
      textAlign: "center",
    },
    body: {
      ...Type.secondary,
      color: theme.textSecondary,
      textAlign: "center",
    },
    featureList: { gap: Space.xs, marginVertical: Space.xs },
    error: {
      color: theme.danger,
      fontSize: 14,
      textAlign: "center",
    },
    primaryBtn: {
      marginTop: Space.xxs,
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
      fontWeight: "600",
    },
    legalSeparator: {
      ...Type.caption,
      color: theme.textTertiary,
    },
    devBtn: {
      alignItems: "center",
      paddingVertical: Space.xs,
    },
    devBtnText: { color: theme.textTertiary, fontSize: 13 },
  });
