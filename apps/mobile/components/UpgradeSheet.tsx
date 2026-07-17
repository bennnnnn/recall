import { Ionicons } from "@expo/vector-icons";
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { Button } from "@/components/Button";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import {
  getMonthlyProPackage,
  isPurchasesConfigured,
  type ProPurchasePackage,
  purchaseProPackage,
  restorePurchases,
} from "@/lib/purchases";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  visible: boolean;
  onClose: () => void;
};

export function UpgradeSheet({ visible, onClose }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = makeStyles(theme);
  const { token, refreshUser } = useAuth();
  const [pkg, setPkg] = useState<ProPurchasePackage | null>(null);
  const [loadingOffer, setLoadingOffer] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const purchasesReady = isPurchasesConfigured();

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
    await api.syncSubscription(token);
    await refreshUser();
    onClose();
  };

  const tryDevUpgrade = async () => {
    if (!token) return;
    try {
      await api.devUpgradePro(token);
      await refreshUser();
      onClose();
    } catch {
      /* dev endpoint unavailable in production */
    }
  };

  const onSubscribe = async () => {
    if (!token || !pkg || busy) return;
    setBusy(true);
    setError(null);
    try {
      const ok = await purchaseProPackage(pkg);
      if (!ok) {
        setError(t("upgrade.purchase_failed"));
        return;
      }
      await syncAfterStore();
    } catch {
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
      variant="bottom"
      animation="fade"
      withHandle={false}
      minBottomPadding={36}
      contentContainerStyle={s.sheet}
    >
      <View style={s.iconWrap}>
        <Ionicons name="sparkles" size={28} color={theme.primary} />
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
  icon: keyof typeof Ionicons.glyphMap;
  text: string;
  theme: Theme;
}) {
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
      <Ionicons name={icon} size={18} color={theme.primary} />
      <Text style={{ flex: 1, ...Type.secondary, color: theme.textSecondary }}>{text}</Text>
    </View>
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    sheet: {
      backgroundColor: theme.bg,
      paddingHorizontal: 24,
      paddingTop: 28,
      gap: 12,
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
    featureList: { gap: 10, marginVertical: 8 },
    error: {
      color: theme.danger,
      fontSize: 14,
      textAlign: "center",
    },
    primaryBtn: {
      marginTop: 4,
    },
    devBtn: {
      alignItems: "center",
      paddingVertical: 10,
    },
    devBtnText: { color: theme.textTertiary, fontSize: 13 },
  });
