import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Modal,
  NativeScrollEvent,
  NativeSyntheticEvent,
  Pressable,
  ScrollView,
  Share,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Avatar } from "@/components/Avatar";
import { StateView } from "@/components/StateView";
import {
  AccordionSection,
  IntegrationPanel,
  ItemRow,
  makeSettingsStyles,
  NavRow,
  Section,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useProjects } from "@/contexts/ProjectsContext";
import { useTodos } from "@/contexts/TodosContext";
import { buildModelPreferences, useModels } from "@/hooks/useModels";
import { UpgradeSheet } from "@/components/UpgradeSheet";
import { api, GoogleCalendarStatus, GoogleGmailStatus, Todo, Usage } from "@/lib/api";
import { describeDueAt } from "@/lib/dueDate";
import { isExpoGo } from "@/lib/expoRuntime";
import { connectGoogleCalendar } from "@/lib/google-calendar";
import { connectGoogleGmail } from "@/lib/google-gmail";
import { LANGUAGES } from "@/lib/i18n";
import { buildListGroups } from "@/lib/listGroups";
import { loadListGroupOrder } from "@/lib/listGroupOrder";
import {
  DEFAULT_REMINDER_LEAD_MINUTES,
  getReminderLeadMinutes,
  REMINDER_LEAD_OPTIONS,
  setReminderLeadMinutes,
  syncReminderLeadFromServer,
} from "@/lib/reminderPrefs";
import { normalizeReminderLeadMinutes } from "@/lib/reminderTiming";
import { formatUsageSummary, usageUsedPercent } from "@/lib/quota";
import { DEFAULT_RESPONSE_TONE, normalizeResponseTone, RESPONSE_TONES } from "@/lib/responseTone";
import { syncTodoReminders } from "@/lib/todoReminders";
import { formatJoinedDate, getDisplayName, sanitizeDisplayName } from "@/lib/profile";
import { useTheme } from "@/lib/theme";

const STYLES = ["short", "balanced", "detailed"] as const;
const PROFILE_STICKY_THRESHOLD = 72;

export default function SettingsScreen() {
  const { token, user, signOut, refreshUser, updateUser } = useAuth();
  const { t } = useTranslation();
  const {
    models: catalogModels,
    isPro,
    autoEnabled,
    modelEnabledSet: enabledModelIds,
  } = useModels();
  const models = catalogModels ?? [];
  const modelEnabledSet = enabledModelIds ?? new Set<string>();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { todos, refresh: refreshTodos } = useTodos();
  const { projects: allProjects, refresh: refreshProjects } = useProjects();
  const projects = useMemo(
    () => allProjects.filter((project) => !project.archived),
    [allProjects],
  );
  const [loading, setLoading] = useState(true);
  const [bootstrapError, setBootstrapError] = useState(false);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [memCount, setMemCount] = useState(0);
  const [saving, setSaving] = useState(false);
  const [editNameVisible, setEditNameVisible] = useState(false);
  const [languagePickerOpen, setLanguagePickerOpen] = useState(false);
  const [stylePickerOpen, setStylePickerOpen] = useState(false);
  const [tonePickerOpen, setTonePickerOpen] = useState(false);
  const [reminderLeadPickerOpen, setReminderLeadPickerOpen] = useState(false);
  const [reminderLeadMinutes, setReminderLeadMinutesState] = useState(
    DEFAULT_REMINDER_LEAD_MINUTES,
  );
  const [upgradeVisible, setUpgradeVisible] = useState(false);
  const [stickyProfile, setStickyProfile] = useState(false);
  const [listGroupOrder, setListGroupOrder] = useState<string[]>([]);
  const [expandedWorkspace, setExpandedWorkspace] = useState({
    projects: false,
    lists: false,
    reminders: false,
  });
  const [modelsExpanded, setModelsExpanded] = useState(false);
  const [integrationsExpanded, setIntegrationsExpanded] = useState(false);
  const [expandedIntegrations, setExpandedIntegrations] = useState({
    calendar: false,
    gmail: false,
  });
  const [calendarStatus, setCalendarStatus] = useState<GoogleCalendarStatus | null>(null);
  const [calendarBusy, setCalendarBusy] = useState(false);
  const [gmailStatus, setGmailStatus] = useState<GoogleGmailStatus | null>(null);
  const [gmailBusy, setGmailBusy] = useState(false);
  const [nameText, setNameText] = useState("");

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    void (async () => {
      const results = await Promise.allSettled([
        refreshUser(),
        api.todayUsage(token),
        api.listMemories(token),
        api.googleCalendarStatus(token),
        api.googleGmailStatus(token),
      ]);
      if (cancelled) return;
      const [, usageR, memsR, calendarR, gmailR] = results;
      if (usageR.status === "fulfilled") setUsage(usageR.value);
      if (memsR.status === "fulfilled") setMemCount(memsR.value.length);
      if (calendarR.status === "fulfilled") setCalendarStatus(calendarR.value);
      if (gmailR.status === "fulfilled") setGmailStatus(gmailR.value);
      setBootstrapError(results[0].status === "rejected" && !user);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [token, refreshUser]);

  useEffect(() => {
    if (!user?.id) return;
    void loadListGroupOrder(user.id).then(setListGroupOrder);
  }, [user?.id]);

  useEffect(() => {
    if (user?.reminder_lead_minutes != null) {
      const minutes = normalizeReminderLeadMinutes(user.reminder_lead_minutes);
      setReminderLeadMinutesState(minutes);
      void syncReminderLeadFromServer(minutes);
      return;
    }
    void getReminderLeadMinutes().then(setReminderLeadMinutesState);
  }, [user?.reminder_lead_minutes]);

  useFocusEffect(
    useCallback(() => {
      if (!loading) {
        void refreshProjects({ silent: true });
        void refreshTodos({ silent: true });
      }
      if (token) {
        void api.todayUsage(token).then(setUsage).catch(() => {});
      }
    }, [loading, refreshProjects, refreshTodos, token]),
  );

  const patch = async (fields: Parameters<typeof updateUser>[0]) => {
    setSaving(true);
    try {
      await updateUser(fields);
    } finally {
      setSaving(false);
    }
  };

  const patchInstant = (fields: Parameters<typeof updateUser>[0]) => {
    void updateUser(fields).catch(() => {
      Alert.alert(t("todos.error"), t("common.error"));
    });
  };

  const saveName = async () => {
    const name = sanitizeDisplayName(nameText);
    setEditNameVisible(false);
    if (!name || name === user?.name) {
      if (nameText.trim() && !name) {
        Alert.alert(t("common.error"), t("settings.name_invalid"));
      }
      return;
    }
    await patch({ name });
  };

  const doExport = async () => {
    if (!token) return;
    try {
      const data = await api.exportData(token);
      await Share.share({ message: JSON.stringify(data, null, 2) });
    } catch (error) {
      const message = error instanceof Error ? error.message : "";
      if (!message.toLowerCase().includes("cancel")) {
        Alert.alert(t("common.error"), t("settings.export_failed"));
      }
    }
  };

  const connectCalendar = async (write = false) => {
    if (!token || calendarBusy) return;
    if (isExpoGo()) {
      Alert.alert(t("settings.calendar_title"), t("settings.calendar_expo_go"));
      return;
    }
    if (calendarStatus?.configured === false) {
      Alert.alert(t("settings.calendar_title"), t("settings.calendar_not_configured"));
      return;
    }
    setCalendarBusy(true);
    try {
      const serverAuthCode = await connectGoogleCalendar({ write });
      const status = await api.connectGoogleCalendar(token, serverAuthCode);
      setCalendarStatus(status);
    } catch (error) {
      const message = error instanceof Error ? error.message : t("settings.calendar_connect_failed");
      if (!message.toLowerCase().includes("cancel")) {
        Alert.alert(t("settings.calendar_title"), message);
      }
    } finally {
      setCalendarBusy(false);
    }
  };

  const disconnectCalendar = () => {
    if (!token || calendarBusy || !calendarStatus?.connected) return;
    Alert.alert(t("settings.calendar_title"), t("settings.calendar_disconnect"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("settings.calendar_disconnect"),
        style: "destructive",
        onPress: async () => {
          setCalendarBusy(true);
          try {
            await api.disconnectGoogleCalendar(token);
            setCalendarStatus({ connected: false, configured: calendarStatus?.configured ?? true });
            Alert.alert(t("settings.calendar_title"), t("settings.calendar_disconnected"));
          } catch {
            Alert.alert(t("settings.calendar_title"), t("settings.calendar_connect_failed"));
          } finally {
            setCalendarBusy(false);
          }
        },
      },
    ]);
  };

  const refreshGmailStatus = async () => {
    if (!token) return;
    const status = await api.googleGmailStatus(token);
    setGmailStatus(status);
  };

  const syncGmail = async () => {
    if (!token || gmailBusy || !gmailStatus?.connected) return;
    setGmailBusy(true);
    try {
      const result = await api.syncGoogleGmail(token);
      await refreshGmailStatus();
      Alert.alert(
        t("settings.gmail_title"),
        t("settings.gmail_sync_done", { count: result.message_count }),
      );
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : t("settings.gmail_sync_failed");
      Alert.alert(t("settings.gmail_title"), message);
    } finally {
      setGmailBusy(false);
    }
  };

  const connectGmail = async () => {
    if (!token || gmailBusy) return;
    if (isExpoGo()) {
      Alert.alert(t("settings.gmail_title"), t("settings.gmail_expo_go"));
      return;
    }
    if (gmailStatus?.configured === false) {
      Alert.alert(t("settings.gmail_title"), t("settings.gmail_not_configured"));
      return;
    }
    Alert.alert(t("settings.gmail_title"), t("settings.gmail_connect_confirm"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("settings.gmail_connect"),
        onPress: () => void runGmailConnect(),
      },
    ]);
  };

  const runGmailConnect = async () => {
    if (!token || gmailBusy) return;
    setGmailBusy(true);
    try {
      const serverAuthCode = await connectGoogleGmail();
      await api.connectGoogleGmail(token, serverAuthCode);
      await api.syncGoogleGmail(token);
      await refreshGmailStatus();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : t("settings.gmail_connect_failed");
      if (message !== "Gmail connect cancelled") {
        Alert.alert(t("settings.gmail_title"), message);
      }
    } finally {
      setGmailBusy(false);
    }
  };

  const disconnectGmail = () => {
    if (!token || gmailBusy || !gmailStatus?.connected) return;
    Alert.alert(t("settings.gmail_title"), t("settings.gmail_disconnect_confirm"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("settings.gmail_disconnect"),
        style: "destructive",
        onPress: async () => {
          setGmailBusy(true);
          try {
            await api.disconnectGoogleGmail(token);
            const status = await api.googleGmailStatus(token);
            setGmailStatus(status);
            Alert.alert(t("settings.gmail_title"), t("settings.gmail_disconnected"));
          } catch {
            Alert.alert(t("settings.gmail_title"), t("settings.gmail_connect_failed"));
          } finally {
            setGmailBusy(false);
          }
        },
      },
    ]);
  };

  const confirmDeleteAccount = () => {
    Alert.alert(t("delete.title"), t("delete.message"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("common.delete"),
        style: "destructive",
        onPress: async () => {
          if (!token) return;
          try {
            await api.deleteAccount(token);
            await signOut();
            router.replace("/login");
          } catch {
            Alert.alert(t("common.error"), t("settings.delete_failed"));
          }
        },
      },
    ]);
  };

  const listGroups = useMemo(
    () =>
      buildListGroups(todos, listGroupOrder, t("lists.default_group")).filter(
        (group) => group.open.length + group.done.length > 0,
      ),
    [todos, listGroupOrder, t],
  );

  const openReminders = useMemo(
    () =>
      [...todos]
        .filter((item) => item.due_at && !item.checked)
        .sort((a, b) => {
          const aDue = a.due_at ? new Date(a.due_at).getTime() : 0;
          const bDue = b.due_at ? new Date(b.due_at).getTime() : 0;
          return aDue - bDue;
        }),
    [todos],
  );

  const connectedIntegrations = useMemo(
    () =>
      (calendarStatus?.connected ? 1 : 0) + (gmailStatus?.connected ? 1 : 0),
    [calendarStatus?.connected, gmailStatus?.connected],
  );

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
            setBootstrapError(false);
            void refreshUser().finally(() => setLoading(false));
          }}
          retryLabel={t("common.retry")}
        />
      </View>
    );
  }

  const usedPct = usage ? usageUsedPercent(usage) : 0;

  const selectedLanguage =
    LANGUAGES.find((lang) => lang.code === user?.locale) ?? LANGUAGES[0];
  const selectedStyle = user?.response_style ?? "balanced";
  const selectedTone = normalizeResponseTone(user?.response_tone ?? DEFAULT_RESPONSE_TONE);

  const patchPreferences = (auto: boolean, modelIds: Set<string>) => {
    if (!auto && modelIds.size === 0) return;
    patchInstant({ enabled_models: buildModelPreferences(auto, modelIds) });
  };

  const toggleAuto = (enabled: boolean) => {
    if (!enabled && modelEnabledSet.size === 0) return;
    patchPreferences(enabled, modelEnabledSet);
  };

  const toggleModel = (modelId: string, enabled: boolean) => {
    if (!user) return;
    const option = models.find((m) => m.id === modelId);
    if (!option?.available) return;
    if (!isPro && option.plan_access === "pro") {
      if (enabled) setUpgradeVisible(true);
      return;
    }
    const next = new Set(modelEnabledSet);
    if (enabled) next.add(modelId);
    else next.delete(modelId);
    if (next.size === 0 && !autoEnabled) return;
    patchPreferences(autoEnabled, next);
  };

  const displayName = getDisplayName(user?.name, t("common.you"));
  const joinedDate = formatJoinedDate(user?.created_at, user?.locale);
  const accountLabel = isPro ? t("settings.account_pro") : t("settings.account_free");

  const toggleWorkspace = (key: keyof typeof expandedWorkspace) => {
    setExpandedWorkspace((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleIntegration = (key: keyof typeof expandedIntegrations) => {
    setExpandedIntegrations((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const onScroll = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    const y = event.nativeEvent.contentOffset.y;
    setStickyProfile(y > PROFILE_STICKY_THRESHOLD);
  };

  return (
    <View style={s.root}>
      {stickyProfile ? (
        <View style={s.stickyProfile}>
          <Avatar name={user?.name ?? null} uri={user?.avatar_url} size={36} />
          <Text style={s.stickyName} numberOfLines={1}>
            {displayName}
          </Text>
          <Text style={[s.stickyAccount, isPro && s.accountPro]}>{accountLabel}</Text>
        </View>
      ) : null}

      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + 24 }]}
        scrollEventThrottle={16}
        onScroll={onScroll}
      >
        <View style={s.profileHeader}>
          <Avatar name={user?.name ?? null} uri={user?.avatar_url} size={64} />
          {joinedDate ? (
            <Text style={s.meta}>{t("settings.joined", { date: joinedDate })}</Text>
          ) : null}
        </View>

        <Section label={t("settings.profile")} styles={s}>
          <Pressable
            style={s.row}
            onPress={() => {
              setNameText(user?.name ?? "");
              setEditNameVisible(true);
            }}
          >
            <View style={s.rowBody}>
              <Text style={s.rowTitle}>{t("settings.name_label")}</Text>
              <Text style={s.meta} numberOfLines={2}>
                {displayName}
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={theme.textTertiary} />
          </Pressable>
          <View style={s.row}>
            <View style={s.rowBody}>
              <Text style={s.rowTitle}>{t("settings.email_label")}</Text>
              <Text style={s.meta} numberOfLines={1}>
                {user?.email}
              </Text>
            </View>
          </View>
          <Pressable
            style={s.row}
            onPress={() => {
              if (!isPro) setUpgradeVisible(true);
            }}
          >
            <View style={s.rowBody}>
              <Text style={s.rowTitle}>{t("settings.account_label")}</Text>
              <Text style={[s.meta, isPro && s.accountPro]}>{accountLabel}</Text>
            </View>
            {!isPro ? (
              <Ionicons name="chevron-forward" size={18} color={theme.textTertiary} />
            ) : null}
          </Pressable>
        </Section>

      {/* Models */}
      <Section label={t("settings.model")} styles={s}>
        <View style={s.row}>
          <View style={s.rowBody}>
            <Text style={s.rowTitle}>{t("settings.model_auto")}</Text>
          </View>
          <Switch
            value={autoEnabled}
            disabled={autoEnabled && modelEnabledSet.size === 0}
            thumbColor={theme.bg}
            trackColor={{ false: theme.border, true: theme.primary }}
            onValueChange={toggleAuto}
          />
        </View>

        <Pressable
          style={s.accordionHeader}
          onPress={() => setModelsExpanded((open) => !open)}
        >
          <Ionicons name="layers-outline" size={19} color={theme.primary} />
          <View style={s.rowBody}>
            <Text style={s.meta}>
              {t("settings.models_enabled", { count: modelEnabledSet.size })}
            </Text>
          </View>
          <Ionicons
            name={modelsExpanded ? "chevron-up" : "chevron-down"}
            size={18}
            color={theme.textTertiary}
          />
        </Pressable>

        {modelsExpanded ? (
          <View style={s.accordionBody}>
            <Text style={s.accordionHint}>{t("settings.model_hint")}</Text>
            {models.map((option) => {
              const proLocked = !isPro && option.plan_access === "pro";
              const enabled = modelEnabledSet.has(option.id) && !proLocked;
              const isLastModel = enabled && modelEnabledSet.size <= 1 && !autoEnabled;
              const switchDisabled =
                isLastModel || (!enabled && !option.available && !proLocked);

              return (
                <View key={option.id} style={s.row}>
                  <View style={s.rowBody}>
                    <Text style={s.rowTitle}>{option.label}</Text>
                  </View>
                  <Switch
                    value={enabled}
                    disabled={switchDisabled}
                    thumbColor={theme.bg}
                    trackColor={{ false: theme.border, true: theme.primary }}
                    onValueChange={(v) => {
                      if (proLocked) {
                        if (v) setUpgradeVisible(true);
                        return;
                      }
                      if (v && !option.available) return;
                      toggleModel(option.id, v);
                    }}
                  />
                </View>
              );
            })}
          </View>
        ) : null}
      </Section>

      {/* Response style */}
      <Section label={t("settings.style")} styles={s}>
        <Pressable
          style={s.dropdown}
          disabled={saving}
          onPress={() => setStylePickerOpen(true)}
        >
          <Text style={s.dropdownText}>{t(`settings.style_${selectedStyle}`)}</Text>
          <Ionicons name="chevron-down" size={18} color={theme.textSecondary} />
        </Pressable>
      </Section>

      {/* Tone */}
      <Section label={t("settings.tone")} hint={t("settings.tone_hint")} styles={s}>
        <Pressable
          style={s.dropdown}
          disabled={saving}
          onPress={() => setTonePickerOpen(true)}
        >
          <Text style={s.dropdownText}>{t(`settings.tone_${selectedTone}`)}</Text>
          <Ionicons name="chevron-down" size={18} color={theme.textSecondary} />
        </Pressable>
      </Section>

      {/* Language */}
      <Section label={t("settings.language")} styles={s}>
        <Pressable
          style={s.dropdown}
          disabled={saving}
          onPress={() => setLanguagePickerOpen(true)}
        >
          <Text style={s.dropdownText}>{selectedLanguage.label}</Text>
          <Ionicons name="chevron-down" size={18} color={theme.textSecondary} />
        </Pressable>
      </Section>

      {/* Location */}
      <Section label={t("settings.location")} styles={s}>
        <Pressable
          style={s.dropdown}
          disabled={saving}
          onPress={() => {
            Alert.prompt(
              t("settings.location_prompt_title"),
              t("settings.location_desc"),
              async (value) => {
                const loc = (value ?? "").trim();
                await patch({ location: loc });
              },
              "default",
              user?.location ?? "",
            );
          }}
        >
          <Text style={s.dropdownText}>
            {user?.location && user.location.trim()
              ? user.location.trim()
              : t("settings.location_not_set")}
          </Text>
          <Ionicons name="chevron-down" size={18} color={theme.textSecondary} />
        </Pressable>
        <Text style={s.meta}>{t("settings.location_desc")}</Text>
      </Section>

      {/* Memory */}
      <Section label={t("settings.memory")} styles={s}>
        <View style={s.row}>
          <View style={s.rowBody}>
            <Text style={s.rowTitle}>{t("settings.memory")}</Text>
            <Text style={s.meta}>{t("settings.memory_desc")}</Text>
          </View>
          <Switch
            value={user?.memory_enabled ?? true}
            thumbColor={theme.bg}
            trackColor={{ false: theme.border, true: theme.primary }}
            onValueChange={(v) => patchInstant({ memory_enabled: v })}
          />
        </View>
        <NavRow
          icon="sparkles-outline"
          title={t("settings.memory_view")}
          meta={
            memCount > 0
              ? t("settings.memory_count", { count: memCount })
              : t("settings.memory_empty")
          }
          onPress={() => router.push("/memory")}
          styles={s}
          theme={theme}
        />
      </Section>

      <Section label={t("settings.notifications")} styles={s}>
        <View style={s.row}>
          <View style={s.rowBody}>
            <Text style={s.rowTitle}>{t("settings.push_notifications")}</Text>
            <Text style={s.meta}>{t("settings.push_notifications_desc")}</Text>
          </View>
          <Switch
            value={user?.push_notifications_enabled ?? true}
            thumbColor={theme.bg}
            trackColor={{ false: theme.border, true: theme.primary }}
            onValueChange={(v) => patchInstant({ push_notifications_enabled: v })}
          />
        </View>
        <Pressable style={s.dropdown} onPress={() => setReminderLeadPickerOpen(true)}>
          <View style={s.rowBody}>
            <Text style={s.rowTitle}>{t("settings.reminder_lead")}</Text>
            <Text style={s.meta}>{t("settings.reminder_lead_desc")}</Text>
          </View>
          <Text style={s.dropdownText}>
            {t("settings.reminder_lead_value", { count: reminderLeadMinutes })}
          </Text>
          <Ionicons name="chevron-down" size={18} color={theme.textSecondary} />
        </Pressable>
      </Section>

      {/* Integrations */}
      <Section label={t("settings.integrations")} styles={s}>
        <Pressable
          style={s.accordionHeader}
          onPress={() => setIntegrationsExpanded((open) => !open)}
        >
          <Ionicons name="extension-puzzle-outline" size={19} color={theme.primary} />
          <View style={s.rowBody}>
            <Text style={s.meta}>
              {connectedIntegrations > 0
                ? t("settings.integrations_connected", { count: connectedIntegrations })
                : t("settings.integrations_manage")}
            </Text>
          </View>
          <Ionicons
            name={integrationsExpanded ? "chevron-up" : "chevron-down"}
            size={18}
            color={theme.textTertiary}
          />
        </Pressable>

        {integrationsExpanded ? (
          <View style={s.accordionBody}>
            <IntegrationPanel
              icon="calendar-outline"
              title={t("settings.calendar_title")}
              showDivider={false}
              summary={
                calendarStatus?.connected && calendarStatus.email
                  ? t("settings.calendar_connected", { email: calendarStatus.email })
                  : t("settings.integration_not_connected")
              }
              expanded={expandedIntegrations.calendar}
              busy={calendarBusy}
              onToggle={() => toggleIntegration("calendar")}
              styles={s}
              theme={theme}
            >
              <Text style={s.meta}>{t("settings.calendar_desc")}</Text>
              {calendarStatus?.connected && !calendarStatus.can_write ? (
                <Pressable onPress={() => void connectCalendar(true)} hitSlop={8}>
                  <Text style={s.linkBtnText}>{t("settings.calendar_upgrade_write")}</Text>
                </Pressable>
              ) : null}
              <View style={s.integrationActions}>
                {calendarBusy ? (
                  <ActivityIndicator color={theme.primary} />
                ) : calendarStatus?.connected ? (
                  <Pressable style={s.linkBtn} onPress={disconnectCalendar} hitSlop={8}>
                    <Text style={s.linkBtnDanger}>{t("settings.calendar_disconnect")}</Text>
                  </Pressable>
                ) : (
                  <Pressable style={s.linkBtn} onPress={() => void connectCalendar(false)} hitSlop={8}>
                    <Text style={s.linkBtnText}>{t("settings.calendar_connect")}</Text>
                  </Pressable>
                )}
              </View>
            </IntegrationPanel>

            <IntegrationPanel
              icon="mail-outline"
              title={t("settings.gmail_title")}
              summary={
                gmailStatus?.connected && gmailStatus.email
                  ? t("settings.gmail_connected", { email: gmailStatus.email })
                  : t("settings.integration_not_connected")
              }
              expanded={expandedIntegrations.gmail}
              busy={gmailBusy}
              onToggle={() => toggleIntegration("gmail")}
              styles={s}
              theme={theme}
            >
              <Text style={s.meta}>{t("settings.gmail_desc")}</Text>
              {gmailStatus?.connected && gmailStatus.last_sync_at ? (
                <Text style={s.meta}>
                  {t("settings.gmail_last_sync", {
                    when: new Date(gmailStatus.last_sync_at).toLocaleString(),
                  })}
                </Text>
              ) : null}
              <View style={s.integrationActions}>
                {gmailBusy ? (
                  <ActivityIndicator color={theme.primary} />
                ) : gmailStatus?.connected ? (
                  <View style={s.rowActions}>
                    <Pressable style={s.linkBtn} onPress={() => void syncGmail()} hitSlop={8}>
                      <Text style={s.linkBtnText}>{t("settings.gmail_sync")}</Text>
                    </Pressable>
                    <Pressable style={s.linkBtn} onPress={disconnectGmail} hitSlop={8}>
                      <Text style={s.linkBtnDanger}>{t("settings.gmail_disconnect")}</Text>
                    </Pressable>
                  </View>
                ) : (
                  <Pressable style={s.linkBtn} onPress={() => void connectGmail()} hitSlop={8}>
                    <Text style={s.linkBtnText}>{t("settings.gmail_connect")}</Text>
                  </Pressable>
                )}
              </View>
            </IntegrationPanel>
          </View>
        ) : null}
      </Section>

      <AccordionSection
        label={t("settings.projects")}
        icon="folder-outline"
        count={projects.length}
        expanded={expandedWorkspace.projects}
        onToggle={() => toggleWorkspace("projects")}
        emptyText={t("settings.projects_empty")}
        viewAllLabel={t("settings.view_all")}
        onViewAll={() => router.push("/projects")}
        styles={s}
        theme={theme}
      >
        {projects.map((project) => (
          <ItemRow
            key={project.id}
            title={project.title}
            meta={project.target_language || undefined}
            onPress={() => router.push(`/projects/${project.id}`)}
            styles={s}
            theme={theme}
          />
        ))}
      </AccordionSection>

      <AccordionSection
        label={t("settings.lists")}
        icon="list-outline"
        count={listGroups.length}
        expanded={expandedWorkspace.lists}
        onToggle={() => toggleWorkspace("lists")}
        emptyText={t("settings.lists_empty")}
        viewAllLabel={t("settings.view_all")}
        onViewAll={() => router.push({ pathname: "/todos", params: { focus: "list" } })}
        styles={s}
        theme={theme}
      >
        {listGroups.map((group) => (
          <ItemRow
            key={group.topic}
            title={group.title}
            meta={t("settings.open_count", { count: group.open.length })}
            onPress={() =>
              router.push({
                pathname: "/todos",
                params: { focus: "list", topic: group.topic },
              })
            }
            styles={s}
            theme={theme}
          />
        ))}
      </AccordionSection>

      <AccordionSection
        label={t("settings.reminders")}
        icon="notifications-outline"
        count={openReminders.length}
        expanded={expandedWorkspace.reminders}
        onToggle={() => toggleWorkspace("reminders")}
        emptyText={t("settings.reminders_empty")}
        viewAllLabel={t("settings.view_all")}
        onViewAll={() => router.push({ pathname: "/todos", params: { focus: "reminders" } })}
        styles={s}
        theme={theme}
      >
        {openReminders.map((todo) => (
          <ItemRow
            key={todo.id}
            title={todo.content}
            meta={describeDueAt(todo.due_at)?.label}
            onPress={() =>
              router.push({
                pathname: "/todos",
                params: { focus: "reminders", highlight: todo.id },
              })
            }
            styles={s}
            theme={theme}
          />
        ))}
      </AccordionSection>

      {/* Usage */}
      {usage && (
        <Section label={t("settings.daily_usage")} styles={s}>
          <View style={s.bar}>
            <View style={[s.barFill, { width: `${usedPct}%` as `${number}%` }]} />
          </View>
          <Text style={s.meta}>
            {formatUsageSummary(usage, isPro, t)}
          </Text>
        </Section>
      )}

      {/* Data & account */}
      <Section styles={s}>
        <NavRow
          icon="download-outline"
          title={t("settings.export")}
          onPress={doExport}
          styles={s}
          theme={theme}
        />
        <NavRow
          icon="shield-checkmark-outline"
          title={t("privacy.title")}
          onPress={() => router.push("/privacy")}
          styles={s}
          theme={theme}
        />
        <NavRow
          icon="trash-outline"
          title={t("settings.delete")}
          onPress={confirmDeleteAccount}
          danger
          styles={s}
          theme={theme}
        />
      </Section>

      <Pressable style={s.signOut} onPress={async () => {
        await signOut();
        router.replace("/login");
      }}>
        <Text style={s.signOutText}>{t("settings.sign_out")}</Text>
      </Pressable>

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

      <Modal visible={languagePickerOpen} transparent animationType="fade">
        <View style={s.pickerBackdrop}>
          <Pressable style={StyleSheet.absoluteFill} onPress={() => setLanguagePickerOpen(false)} />
          <View style={s.pickerSheet}>
            <Text style={s.pickerTitle}>{t("settings.language")}</Text>
            {LANGUAGES.map((lang) => {
              const active = user?.locale === lang.code;
              return (
                <Pressable
                  key={lang.code}
                  style={[s.pickerOption, active && s.pickerOptionActive]}
                  disabled={saving}
                  onPress={() => {
                    setLanguagePickerOpen(false);
                    if (!active) void patch({ locale: lang.code });
                  }}
                >
                  <Text style={[s.pickerOptionText, active && s.pickerOptionTextActive]}>
                    {lang.label}
                  </Text>
                  {active ? (
                    <Ionicons name="checkmark" size={18} color={theme.primary} />
                  ) : null}
                </Pressable>
              );
            })}
          </View>
        </View>
      </Modal>

      <Modal visible={tonePickerOpen} transparent animationType="fade">
        <View style={s.pickerBackdrop}>
          <Pressable style={StyleSheet.absoluteFill} onPress={() => setTonePickerOpen(false)} />
          <View style={s.pickerSheet}>
            <Text style={s.pickerTitle}>{t("settings.tone")}</Text>
            {RESPONSE_TONES.map((tone) => {
              const active = selectedTone === tone;
              return (
                <Pressable
                  key={tone}
                  style={[s.pickerOption, active && s.pickerOptionActive]}
                  disabled={saving}
                  onPress={() => {
                    setTonePickerOpen(false);
                    if (!active) void patch({ response_tone: tone });
                  }}
                >
                  <Text style={[s.pickerOptionText, active && s.pickerOptionTextActive]}>
                    {t(`settings.tone_${tone}`)}
                  </Text>
                  {active ? (
                    <Ionicons name="checkmark" size={18} color={theme.primary} />
                  ) : null}
                </Pressable>
              );
            })}
          </View>
        </View>
      </Modal>

      <Modal visible={stylePickerOpen} transparent animationType="fade">
        <View style={s.pickerBackdrop}>
          <Pressable style={StyleSheet.absoluteFill} onPress={() => setStylePickerOpen(false)} />
          <View style={s.pickerSheet}>
            <Text style={s.pickerTitle}>{t("settings.style")}</Text>
            {STYLES.map((st) => {
              const active = selectedStyle === st;
              return (
                <Pressable
                  key={st}
                  style={[s.pickerOption, active && s.pickerOptionActive]}
                  disabled={saving}
                  onPress={() => {
                    setStylePickerOpen(false);
                    if (!active) void patch({ response_style: st });
                  }}
                >
                  <Text style={[s.pickerOptionText, active && s.pickerOptionTextActive]}>
                    {t(`settings.style_${st}`)}
                  </Text>
                  {active ? (
                    <Ionicons name="checkmark" size={18} color={theme.primary} />
                  ) : null}
                </Pressable>
              );
            })}
          </View>
        </View>
      </Modal>

      <Modal visible={reminderLeadPickerOpen} transparent animationType="fade">
        <View style={s.pickerBackdrop}>
          <Pressable
            style={StyleSheet.absoluteFill}
            onPress={() => setReminderLeadPickerOpen(false)}
          />
          <View style={s.pickerSheet}>
            <Text style={s.pickerTitle}>{t("settings.reminder_lead")}</Text>
            {REMINDER_LEAD_OPTIONS.map((minutes) => {
              const active = reminderLeadMinutes === minutes;
              return (
                <Pressable
                  key={minutes}
                  style={[s.pickerOption, active && s.pickerOptionActive]}
                  onPress={() => {
                    setReminderLeadPickerOpen(false);
                    if (active) return;
                    setReminderLeadMinutesState(minutes);
                    void (async () => {
                      await setReminderLeadMinutes(minutes);
                      try {
                        await updateUser({ reminder_lead_minutes: minutes });
                      } catch {
                        Alert.alert(t("todos.error"), t("common.error"));
                      }
                      await syncTodoReminders(todos);
                    })();
                  }}
                >
                  <Text style={[s.pickerOptionText, active && s.pickerOptionTextActive]}>
                    {t("settings.reminder_lead_value", { count: minutes })}
                  </Text>
                  {active ? (
                    <Ionicons name="checkmark" size={18} color={theme.primary} />
                  ) : null}
                </Pressable>
              );
            })}
          </View>
        </View>
      </Modal>

      <UpgradeSheet visible={upgradeVisible} onClose={() => setUpgradeVisible(false)} />
      </ScrollView>
    </View>
  );
}
