import { useCallback, useMemo, useState } from "react";
import {
  Alert,
  Modal,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { AvatarUsageRing } from "@/components/AvatarUsageRing";
import { UpgradeSheet } from "@/components/UpgradeSheet";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useModels } from "@/hooks/useModels";
import { api } from "@/lib/api";
import { LANGUAGES } from "@/lib/i18n";
import { usageRemainingPercent } from "@/lib/quota";
import { getDisplayName, sanitizeDisplayName } from "@/lib/profile";
import { useTheme } from "@/lib/theme";

export default function SettingsScreen() {
  const { token, user, signOut, updateUser } = useAuth();
  const { t } = useTranslation();
  const { isPro, autoEnabled, modelEnabledSet } = useModels();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const router = useRouter();

  const [usage, setUsage] = useState<Awaited<ReturnType<typeof api.todayUsage>> | null>(null);
  const [connectedCount, setConnectedCount] = useState(0);
  const [editNameVisible, setEditNameVisible] = useState(false);
  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const [nameText, setNameText] = useState("");

  const refreshSummary = useCallback(async () => {
    if (!token) return;
    const [usageR, calendarR, gmailR] = await Promise.allSettled([
      api.todayUsage(token),
      api.googleCalendarStatus(token),
      api.googleGmailStatus(token),
    ]);
    if (usageR.status === "fulfilled") setUsage(usageR.value);
    let count = 0;
    if (calendarR.status === "fulfilled" && calendarR.value.connected) count += 1;
    if (gmailR.status === "fulfilled" && gmailR.value.connected) count += 1;
    setConnectedCount(count);
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      void refreshSummary();
    }, [refreshSummary]),
  );

  const saveName = async () => {
    const name = sanitizeDisplayName(nameText);
    setEditNameVisible(false);
    if (!name || name === user?.name) {
      if (nameText.trim() && !name) {
        Alert.alert(t("common.error"), t("settings.name_invalid"));
      }
      return;
    }
    try {
      await updateUser({ name });
    } catch {
      Alert.alert(t("common.error"), t("common.error"));
    }
  };

  if (!token) return <Redirect href="/login" />;

  const remainingPct = usage ? Math.round(usageRemainingPercent(usage)) : null;
  const displayName = getDisplayName(user?.name, t("common.you"));
  const accountLabel = isPro ? t("settings.account_pro") : t("settings.account_free");
  const selectedLanguage =
    LANGUAGES.find((lang) => lang.code === user?.locale) ?? LANGUAGES[0];
  const modelsValue = autoEnabled
    ? t("settings.model_auto")
    : t("settings.models_enabled", { count: modelEnabledSet.size });
  const memoryValue = user?.memory_enabled ? t("settings.on") : t("settings.off");
  const integrationsValue =
    connectedCount > 0
      ? t("settings.integrations_connected", { count: connectedCount })
      : t("settings.integration_not_connected");

  return (
    <View style={s.root}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + 24 }]}
      >
        <View style={s.profileHeader}>
          <AvatarUsageRing
            name={user?.name ?? null}
            uri={user?.avatar_url}
            size={72}
            remainingPct={remainingPct}
          />
          <Text style={s.profileName}>{displayName}</Text>
          <Text style={[s.profilePlan, isPro && s.accountPro]}>{accountLabel}</Text>
        </View>

        <SettingsGroup label={t("settings.profile")} styles={s}>
          <SettingsLinkRow
            title={t("settings.name_label")}
            value={displayName}
            onPress={() => {
              setNameText(user?.name ?? "");
              setEditNameVisible(true);
            }}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <View style={s.menuRow}>
            <Text style={[s.rowTitle, s.menuRowTitle]}>{t("settings.email_label")}</Text>
            <Text style={s.linkValue} numberOfLines={1}>
              {user?.email}
            </Text>
          </View>
          <View style={s.menuSeparator} />
          {isPro ? (
            <View style={s.menuRow}>
              <Text style={[s.rowTitle, s.menuRowTitle]}>{t("settings.account_label")}</Text>
              <Text style={s.linkValue}>{accountLabel}</Text>
            </View>
          ) : (
            <SettingsLinkRow
              title={t("settings.account_label")}
              value={accountLabel}
              onPress={() => setUpgradeVisible(true)}
              styles={s}
              theme={theme}
            />
          )}
        </SettingsGroup>

        <SettingsGroup label={t("settings.general")} styles={s}>
          <SettingsLinkRow
            title={t("settings.model")}
            value={modelsValue}
            onPress={() => router.push("/settings/models")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.personalization")}
            value={selectedLanguage.label}
            onPress={() => router.push("/settings/preferences")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.learning.title")}
            onPress={() => router.push("/settings/learning")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.memory")}
            value={memoryValue}
            onPress={() => router.push("/settings/memory-settings")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.notifications")}
            value={user?.push_notifications_enabled ? t("settings.on") : t("settings.off")}
            onPress={() => router.push("/settings/notifications")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.integrations")}
            value={integrationsValue}
            onPress={() => router.push("/settings/integrations")}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>

        <SettingsGroup styles={s}>
          <SettingsLinkRow
            title={t("settings.data_controls")}
            onPress={() => router.push("/settings/data-controls")}
            styles={s}
            theme={theme}
          />
          <View style={s.menuSeparator} />
          <SettingsLinkRow
            title={t("settings.about")}
            onPress={() => router.push("/settings/about")}
            styles={s}
            theme={theme}
          />
        </SettingsGroup>

        <Pressable
          style={s.signOut}
          onPress={async () => {
            await signOut();
            router.replace("/login");
          }}
        >
          <Text style={s.signOutText}>{t("settings.sign_out")}</Text>
        </Pressable>
      </ScrollView>

      <Modal
        visible={editNameVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setEditNameVisible(false)}
      >
        <Pressable style={s.mOverlay} onPress={() => setEditNameVisible(false)}>
          <Pressable style={s.mSheet} onPress={(e) => e.stopPropagation()}>
            <Text style={s.mTitle}>{t("settings.your_name")}</Text>
            <TextInput
              style={s.mInput}
              value={nameText}
              onChangeText={setNameText}
              autoFocus
              returnKeyType="done"
              onSubmitEditing={saveName}
              maxLength={80}
            />
            <View style={s.mActions}>
              <Pressable style={s.mCancel} onPress={() => setEditNameVisible(false)}>
                <Text style={s.mCancelText}>{t("settings.cancel")}</Text>
              </Pressable>
              <Pressable style={s.mSave} onPress={saveName}>
                <Text style={s.mSaveText}>{t("settings.save")}</Text>
              </Pressable>
            </View>
          </Pressable>
        </Pressable>
      </Modal>

      <UpgradeSheet visible={upgradeVisible} onClose={() => setUpgradeVisible(false)} />
    </View>
  );
}
