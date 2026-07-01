import { useCallback, useEffect, useMemo, useState } from "react";
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
import { StateView } from "@/components/StateView";
import { UpgradeSheet } from "@/components/UpgradeSheet";
import {
  makeSettingsStyles,
  NavRow,
  SettingsGroup,
  SettingsLinkRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useSettingsIntegrations } from "@/hooks/useSettingsIntegrations";
import { useModels } from "@/hooks/useModels";
import { api } from "@/lib/api";
import { LANGUAGES } from "@/lib/i18n";
import { usageRemainingPercent } from "@/lib/quota";
import { getDisplayName, sanitizeDisplayName } from "@/lib/profile";
import { useTheme } from "@/lib/theme";

export default function SettingsScreen() {
  const { token, user, signOut, refreshUser, updateUser } = useAuth();
  const { t } = useTranslation();
  const { isPro, autoEnabled, modelEnabledSet, refresh: refreshModels } = useModels();
  const { connectedCount } = useSettingsIntegrations();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [bootstrapError, setBootstrapError] = useState(false);
  const [usage, setUsage] = useState<Awaited<ReturnType<typeof api.todayUsage>> | null>(null);
  const [memCount, setMemCount] = useState(0);
  const [editNameVisible, setEditNameVisible] = useState(false);
  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const [nameText, setNameText] = useState("");

  const loadBootstrap = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }
    setBootstrapError(false);
    const results = await Promise.allSettled([
      refreshUser(),
      api.todayUsage(token),
      api.listMemories(token),
    ]);
    const [userR, usageR, memsR] = results;
    if (usageR.status === "fulfilled") setUsage(usageR.value);
    if (memsR.status === "fulfilled") setMemCount(memsR.value.length);
    if (userR.status === "rejected") setBootstrapError(true);
  }, [token, refreshUser]);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        await loadBootstrap();
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, loadBootstrap]);

  useFocusEffect(
    useCallback(() => {
      void refreshModels();
      if (token) {
        void api.todayUsage(token).then(setUsage).catch(() => {});
      }
    }, [refreshModels, token]),
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

  if (loading) {
    return (
      <View style={s.center}>
        <StateView variant="loading" />
      </View>
    );
  }

  if (bootstrapError && !user) {
    return (
      <View style={s.center}>
        <StateView
          variant="error"
          title={t("common.error")}
          onRetry={() => {
            setLoading(true);
            void loadBootstrap().finally(() => setLoading(false));
          }}
          retryLabel={t("common.retry")}
        />
      </View>
    );
  }

  const remainingPct = usage ? Math.round(usageRemainingPercent(usage)) : null;
  const displayName = getDisplayName(user?.name, t("common.you"));
  const accountLabel = isPro ? t("settings.account_pro") : t("settings.account_free");
  const selectedLanguage =
    LANGUAGES.find((lang) => lang.code === user?.locale) ?? LANGUAGES[0];
  const modelsValue = autoEnabled
    ? t("settings.model_auto")
    : t("settings.models_enabled", { count: modelEnabledSet.size });
  const memoryValue =
    memCount > 0
      ? t("settings.memory_count", { count: memCount })
      : user?.memory_enabled
        ? t("settings.on")
        : t("settings.off");
  const integrationsValue =
    connectedCount > 0
      ? t("settings.integrations_connected", { count: connectedCount })
      : undefined;

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

        <View style={s.section}>
          <Text style={s.sectionLabel}>{t("settings.profile")}</Text>
          <View style={s.menuStack}>
            <View style={s.footerGroup}>
              <Pressable
                style={s.menuRow}
                onPress={() => {
                  setNameText(user?.name ?? "");
                  setEditNameVisible(true);
                }}
              >
                <Text style={s.rowTitle}>{t("settings.name_label")}</Text>
                <View style={s.linkTrailing}>
                  <Text style={s.linkValue} numberOfLines={1}>
                    {displayName}
                  </Text>
                  <Ionicons name="chevron-forward" size={18} color={theme.textTertiary} />
                </View>
              </Pressable>
            </View>
            <View style={s.footerGroup}>
              <View style={s.menuRow}>
                <Text style={s.rowTitle}>{t("settings.email_label")}</Text>
                <Text style={s.linkValue} numberOfLines={1}>
                  {user?.email}
                </Text>
              </View>
            </View>
            <View style={s.footerGroup}>
              <Pressable
                style={s.menuRow}
                onPress={() => {
                  if (!isPro) setUpgradeVisible(true);
                }}
              >
                <Text style={s.rowTitle}>{t("settings.account_label")}</Text>
                <View style={s.linkTrailing}>
                  <Text style={[s.linkValue, isPro && s.accountPro]}>{accountLabel}</Text>
                  {!isPro ? (
                    <Ionicons name="chevron-forward" size={18} color={theme.textTertiary} />
                  ) : null}
                </View>
              </Pressable>
            </View>
          </View>
        </View>

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

        <View style={s.footerBand}>
          <View style={s.menuStack}>
            <View style={s.footerGroup}>
              <NavRow
                icon="server-outline"
                title={t("settings.data_controls")}
                onPress={() => router.push("/settings/data-controls")}
                compact
                styles={s}
                theme={theme}
              />
            </View>
            <View style={s.footerGroup}>
              <NavRow
                icon="information-circle-outline"
                title={t("settings.about")}
                onPress={() => router.push("/settings/about")}
                compact
                styles={s}
                theme={theme}
              />
            </View>
          </View>
        </View>

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
