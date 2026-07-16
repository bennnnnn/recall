import { Ionicons } from "@expo/vector-icons";
import { useEffect, useState } from "react";
import { ActivityIndicator, Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

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

type Props = {
  visible: boolean;
  onClose: () => void;
};

export function UpgradeSheet({ visible, onClose }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = makeStyles(theme);
  const insets = useSafeAreaInsets();
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
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={s.backdrop}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} />
        <View style={[s.sheet, { paddingBottom: Math.max(insets.bottom, 36) }]}>
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
              <Pressable
                style={[s.primaryBtn, (busy || loadingOffer || !pkg) && s.primaryBtnDisabled]}
                disabled={busy || loadingOffer || !pkg}
                onPress={() => void onSubscribe()}
              >
                {busy || loadingOffer ? (
                  <ActivityIndicator color={theme.onPrimary} />
                ) : (
                  <Text style={s.primaryBtnText}>
                    {t("upgrade.subscribe", { price: priceLabel })}
                  </Text>
                )}
              </Pressable>
              <Pressable style={s.secondaryBtn} disabled={busy} onPress={() => void onRestore()}>
                <Text style={s.secondaryBtnText}>{t("upgrade.restore")}</Text>
              </Pressable>
            </>
          ) : (
            <Pressable style={s.primaryBtn} onPress={onClose}>
              <Text style={s.primaryBtnText}>{t("upgrade.coming_soon")}</Text>
            </Pressable>
          )}
          {__DEV__ ? (
            <Pressable style={s.devBtn} onPress={() => void tryDevUpgrade()}>
              <Text style={s.devBtnText}>{t("upgrade.dev_enable")}</Text>
            </Pressable>
          ) : null}
        </View>
      </View>
    </Modal>
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
      <Text style={{ flex: 1, fontSize: 15, color: theme.textSecondary, lineHeight: 21 }}>{text}</Text>
    </View>
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    backdrop: {
      flex: 1,
      backgroundColor: theme.scrim,
      justifyContent: "flex-end",
    },
    sheet: {
      backgroundColor: theme.bg,
      borderTopLeftRadius: 20,
      borderTopRightRadius: 20,
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
      fontSize: 15,
      color: theme.textSecondary,
      textAlign: "center",
      lineHeight: 22,
    },
    featureList: { gap: 10, marginVertical: 8 },
    error: {
      color: theme.danger,
      fontSize: 14,
      textAlign: "center",
    },
    primaryBtn: {
      backgroundColor: theme.primary,
      borderRadius: 14,
      paddingVertical: 14,
      alignItems: "center",
      marginTop: 4,
      minHeight: 48,
      justifyContent: "center",
    },
    primaryBtnDisabled: { opacity: 0.6 },
    primaryBtnText: { color: theme.onPrimary, fontSize: 16, fontWeight: "700" },
    secondaryBtn: {
      alignItems: "center",
      paddingVertical: 10,
    },
    secondaryBtnText: { color: theme.primary, fontSize: 15, fontWeight: "600" },
    devBtn: {
      alignItems: "center",
      paddingVertical: 10,
    },
    devBtnText: { color: theme.textTertiary, fontSize: 13 },
  });
