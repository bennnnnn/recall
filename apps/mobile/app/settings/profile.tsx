import { useMemo, useRef, useState } from "react";
import { Alert, Linking, Platform, ScrollView, View } from "react-native";
import { Redirect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { UpgradeSheet } from "@/components/UpgradeSheet";
import { SettingsFieldSheet } from "@/components/settings/SettingsFieldSheet";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
  SettingsValueRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useModels } from "@/hooks/useModels";
import { type User } from "@/lib/api";
import { getDisplayName, sanitizeDisplayName } from "@/lib/profile";
import { restorePurchases } from "@/lib/purchases";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

function manageSubscriptionUrl(): string {
  return Platform.OS === "ios"
    ? "https://apps.apple.com/account/subscriptions"
    : "https://play.google.com/store/account/subscriptions";
}

function signInLabel(
  provider: User["sign_in_provider"] | undefined,
  t: (key: string) => string,
): string {
  if (provider === "google") return t("settings.sign_in_google");
  if (provider === "apple") return t("settings.sign_in_apple");
  return t("settings.sign_in_dev");
}

export default function AccountSettingsScreen() {
  const { token, user, updateUser } = useAuth();
  const { t } = useTranslation();
  const { isPro } = useModels();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const feedback = useActionFeedbackOptional();

  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const [editName, setEditName] = useState(false);
  const [fieldText, setFieldText] = useState("");
  const [fieldSaving, setFieldSaving] = useState(false);
  const [restoreBusy, setRestoreBusy] = useState(false);
  const fieldSavingRef = useRef(false);

  const openName = () => {
    if (!user) return;
    setFieldText(user.name ?? "");
    setEditName(true);
  };

  const saveName = async () => {
    if (fieldSavingRef.current || !user) return;
    const name = sanitizeDisplayName(fieldText);
    if (!name) {
      if (fieldText.trim()) Alert.alert(t("common.error"), t("settings.name_invalid"));
      return;
    }
    if (name === user.name) {
      setEditName(false);
      return;
    }
    fieldSavingRef.current = true;
    setFieldSaving(true);
    try {
      await updateUser({ name });
      setEditName(false);
    } catch {
      if (feedback) feedback.error(t("common.error"));
      else Alert.alert(t("common.error"), t("common.error"));
    } finally {
      fieldSavingRef.current = false;
      setFieldSaving(false);
    }
  };

  const restore = async () => {
    if (restoreBusy) return;
    setRestoreBusy(true);
    try {
      const ok = await restorePurchases();
      if (ok) {
        feedback?.success(t("settings.restore_purchases_ok"));
      } else {
        feedback?.error(t("settings.restore_purchases_none"));
      }
    } catch {
      feedback?.error(t("common.error"));
    } finally {
      setRestoreBusy(false);
    }
  };

  if (!token) return <Redirect href="/login" />;

  const displayName = getDisplayName(user?.name, t("common.you"));
  const planLabel = isPro ? t("settings.account_pro") : t("settings.account_free");

  return (
    <View style={s.root}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
      >
        <SettingsGroup styles={s}>
          <SettingsLinkRow
            title={t("settings.name_label")}
            value={displayName}
            onPress={openName}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsValueRow
            title={t("settings.email")}
            value={user?.email ?? ""}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsValueRow
            title={t("settings.sign_in_method")}
            value={signInLabel(user?.sign_in_provider, t)}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>

        <SettingsGroup styles={s}>
          {isPro ? (
            <>
              <SettingsValueRow
                title={t("settings.plan_label")}
                value={planLabel}
                styles={s}
                theme={theme}
              />
              <View style={s.menuSeparator} />
              <SettingsLinkRow
                title={t("settings.manage_subscription")}
                onPress={() => void Linking.openURL(manageSubscriptionUrl())}
                styles={s}
                theme={theme}
              />
              <View style={s.menuSeparator} />
              <SettingsLinkRow
                title={t("settings.restore_purchases")}
                onPress={() => void restore()}
                styles={s}
                theme={theme}
              />
            </>
          ) : (
            <SettingsLinkRow
              title={t("settings.plan_label")}
              value={planLabel}
              onPress={() => setUpgradeVisible(true)}
              styles={s}
              theme={theme}
            />
          )}
        </SettingsGroup>
      </ScrollView>

      <SettingsFieldSheet
        visible={editName}
        title={t("settings.your_name")}
        value={fieldText}
        onChangeText={setFieldText}
        onClose={() => setEditName(false)}
        onSave={() => void saveName()}
        saving={fieldSaving}
        maxLength={80}
      />

      <UpgradeSheet
        visible={upgradeVisible}
        source="settings"
        onClose={() => setUpgradeVisible(false)}
      />
    </View>
  );
}
