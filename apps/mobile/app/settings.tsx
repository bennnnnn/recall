import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Modal,
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
import { Redirect, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { Avatar } from "@/components/Avatar";
import { useAuth } from "@/contexts/AuthContext";
import { api, Usage } from "@/lib/api";
import { LANGUAGES } from "@/lib/i18n";
import { Theme, useTheme } from "@/lib/theme";

const MODELS = ["auto", "free-chat", "smart-chat"] as const;
const STYLES = ["short", "balanced", "detailed"] as const;
const MODEL_LABEL: Record<string, string> = {
  auto: "Auto",
  "free-chat": "Flash",
  "smart-chat": "Pro",
};

export default function SettingsScreen() {
  const { token, user, signOut, refreshUser, updateUser } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [memCount, setMemCount] = useState(0);
  const [saving, setSaving] = useState(false);
  const [editNameVisible, setEditNameVisible] = useState(false);
  const [nameText, setNameText] = useState("");
  const [customText, setCustomText] = useState(user?.custom_instructions ?? "");
  const customSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    Promise.all([refreshUser(), api.todayUsage(token), api.listMemories(token)])
      .then(([, u, mems]) => {
        if (cancelled) return;
        setUsage(u);
        setMemCount(mems.length);
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, refreshUser]);

  // Sync customText from the server unless the user is actively typing.
  const customDirtyRef = useRef(false);
  useEffect(() => {
    if (!customDirtyRef.current) {
      setCustomText(user?.custom_instructions ?? "");
    }
  }, [user?.custom_instructions]);

  useEffect(() => {
    return () => {
      if (customSaveTimer.current) clearTimeout(customSaveTimer.current);
    };
  }, []);

  const patch = async (fields: Parameters<typeof updateUser>[0]) => {
    setSaving(true);
    try {
      await updateUser(fields);
    } finally {
      setSaving(false);
    }
  };

  const saveCustom = (value: string) => {
    customDirtyRef.current = true;
    setCustomText(value);
    if (customSaveTimer.current) clearTimeout(customSaveTimer.current);
    customSaveTimer.current = setTimeout(() => {
      const trimmed = value.trim();
      if (trimmed !== (user?.custom_instructions ?? "")) {
        patch({ custom_instructions: trimmed || "" }).finally(() => {
          customDirtyRef.current = false;
        });
      } else {
        customDirtyRef.current = false;
      }
    }, 600);
  };

  const saveName = async () => {
    const name = nameText.trim();
    setEditNameVisible(false);
    if (!name || name === user?.name) return;
    await patch({ name });
  };

  const doExport = async () => {
    if (!token) return;
    try {
      const data = await api.exportData(token);
      await Share.share({ message: JSON.stringify(data, null, 2) });
    } catch {
      /* cancelled or failed */
    }
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
          } catch {
            /* ignore */
          }
          await signOut();
          router.replace("/login");
        },
      },
    ]);
  };

  if (!token) return <Redirect href="/login" />;

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator color={theme.primary} />
      </View>
    );
  }

  const usedPct = usage
    ? Math.min(100, ((usage.input_tokens + usage.output_tokens) / usage.daily_limit) * 100)
    : 0;

  return (
    <ScrollView style={s.root} contentContainerStyle={s.content}>
      {/* Profile header */}
      <View style={s.profile}>
        <Avatar name={user?.name ?? null} uri={user?.avatar_url} size={64} />
        <Text style={s.profileName}>{user?.name ?? t("common.you")}</Text>
        <Text style={s.profileEmail}>{user?.email}</Text>
        <Pressable
          style={s.editName}
          hitSlop={8}
          onPress={() => {
            setNameText(user?.name ?? "");
            setEditNameVisible(true);
          }}
        >
          <Ionicons name="pencil-outline" size={14} color={theme.primary} />
          <Text style={s.editNameText}>{t("settings.your_name")}</Text>
        </Pressable>
      </View>

      {/* Model + style */}
      <Section label={t("settings.model")} styles={s}>
        <View style={s.chipRow}>
          {MODELS.map((mdl) => (
            <Chip
              key={mdl}
              label={MODEL_LABEL[mdl]}
              active={user?.default_model === mdl}
              disabled={saving}
              onPress={() => patch({ default_model: mdl })}
              styles={s}
            />
          ))}
        </View>
        <Text style={s.subLabel}>{t("settings.style")}</Text>
        <View style={s.chipRow}>
          {STYLES.map((st) => (
            <Chip
              key={st}
              label={t(`settings.style_${st}`)}
              active={user?.response_style === st}
              disabled={saving}
              onPress={() => patch({ response_style: st })}
              styles={s}
            />
          ))}
        </View>
      </Section>

      {/* Custom instructions */}
      <Section
        label={t("settings.custom_instructions")}
        hint={t("settings.custom_instructions_hint")}
        styles={s}
      >
        <View style={s.customWrap}>
          <TextInput
            style={s.customInput}
            placeholder={t("settings.custom_instructions_placeholder")}
            placeholderTextColor={theme.textTertiary}
            value={customText}
            onChangeText={saveCustom}
            multiline
            numberOfLines={5}
            textAlignVertical="top"
            blurOnSubmit
          />
          {user?.custom_instructions ? (
            <Pressable
              style={s.clearBtn}
              onPress={() => patch({ custom_instructions: "" })}
              hitSlop={6}
            >
              <Ionicons name="close-circle" size={20} color={theme.textTertiary} />
            </Pressable>
          ) : null}
        </View>
      </Section>

      {/* Language */}
      <Section label={t("settings.language")} styles={s}>
        <View style={s.chipRow}>
          {LANGUAGES.map((lang) => (
            <Chip
              key={lang.code}
              label={lang.label}
              active={user?.locale === lang.code}
              disabled={saving}
              onPress={() => patch({ locale: lang.code })}
              styles={s}
            />
          ))}
        </View>
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
            disabled={saving}
            thumbColor={theme.bg}
            trackColor={{ false: theme.border, true: theme.primary }}
            onValueChange={(v) => patch({ memory_enabled: v })}
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

      {/* Usage */}
      {usage && (
        <Section label={t("settings.free_plan")} styles={s}>
          <View style={s.bar}>
            <View style={[s.barFill, { width: `${usedPct}%` as `${number}%` }]} />
          </View>
          <Text style={s.meta}>
            {usage.remaining <= 0
              ? t("settings.usage_exhausted")
              : t("settings.usage_left", {
                  pct: Math.round((usage.remaining / usage.daily_limit) * 100),
                })}
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
    </ScrollView>
  );
}

function Section({
  label,
  hint,
  children,
  styles,
}: {
  label?: string;
  hint?: string;
  children: ReactNode;
  styles: ReturnType<typeof makeStyles>;
}) {
  return (
    <View style={styles.section}>
      {label ? <Text style={styles.sectionLabel}>{label}</Text> : null}
      {hint ? <Text style={styles.sectionHint}>{hint}</Text> : null}
      <View style={styles.group}>{children}</View>
    </View>
  );
}

function Chip({
  label,
  active,
  disabled,
  onPress,
  styles,
}: {
  label: string;
  active: boolean;
  disabled?: boolean;
  onPress: () => void;
  styles: ReturnType<typeof makeStyles>;
}) {
  return (
    <Pressable
      disabled={disabled}
      style={[styles.chip, active && styles.chipActive]}
      onPress={onPress}
    >
      <Text style={active ? styles.chipTextActive : styles.chipText}>{label}</Text>
    </Pressable>
  );
}

function NavRow({
  icon,
  title,
  meta,
  onPress,
  danger,
  styles,
  theme,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  meta?: string;
  onPress: () => void;
  danger?: boolean;
  styles: ReturnType<typeof makeStyles>;
  theme: Theme;
}) {
  return (
    <Pressable style={styles.row} onPress={onPress}>
      <Ionicons name={icon} size={19} color={danger ? theme.danger : theme.primary} />
      <View style={styles.rowBody}>
        <Text style={[styles.rowTitle, danger && { color: theme.danger }]}>{title}</Text>
        {meta ? <Text style={styles.meta}>{meta}</Text> : null}
      </View>
      {!danger ? (
        <Ionicons name="chevron-forward" size={18} color={theme.textTertiary} />
      ) : null}
    </Pressable>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: t.bg },
    root: { flex: 1, backgroundColor: t.bg },
    content: { padding: 16, paddingBottom: 40 },

    profile: { alignItems: "center", paddingVertical: 16, gap: 6 },
    profileName: { fontSize: 20, fontWeight: "700", color: t.text, marginTop: 4 },
    profileEmail: { fontSize: 14, color: t.textSecondary },
    editName: {
      flexDirection: "row",
      alignItems: "center",
      gap: 5,
      marginTop: 6,
      paddingHorizontal: 12,
      paddingVertical: 6,
      borderRadius: 999,
      backgroundColor: t.surface,
    },
    editNameText: { fontSize: 13, fontWeight: "600", color: t.primary },

    section: { marginTop: 20 },
    sectionLabel: {
      fontSize: 12,
      fontWeight: "700",
      color: t.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
      marginLeft: 4,
      marginBottom: 8,
    },
    sectionHint: { fontSize: 13, color: t.textSecondary, marginLeft: 4, marginBottom: 8 },
    group: {
      backgroundColor: t.surface,
      borderRadius: 16,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      padding: 14,
      gap: 10,
    },

    subLabel: { fontSize: 13, color: t.textSecondary, marginTop: 6 },
    chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
    chip: {
      borderRadius: 999,
      borderWidth: 1,
      borderColor: t.border,
      paddingHorizontal: 14,
      paddingVertical: 7,
      backgroundColor: t.bg,
    },
    chipActive: { backgroundColor: t.primary, borderColor: t.primary },
    chipText: { color: t.text, fontSize: 13, textTransform: "capitalize" },
    chipTextActive: { color: "#fff", fontSize: 13, fontWeight: "600", textTransform: "capitalize" },

    row: { flexDirection: "row", alignItems: "center", gap: 12, minHeight: 32 },
    rowBody: { flex: 1 },
    rowTitle: { fontSize: 15, fontWeight: "600", color: t.text },
    meta: { fontSize: 13, color: t.textTertiary, marginTop: 1 },

    customWrap: { position: "relative" },
    customInput: {
      backgroundColor: t.bg,
      borderRadius: 12,
      padding: 10,
      fontSize: 14,
      lineHeight: 20,
      color: t.text,
      borderWidth: 1,
      borderColor: t.border,
      minHeight: 96,
      maxHeight: 200,
    },
    clearBtn: { position: "absolute", top: 8, right: 8 },

    bar: { height: 6, borderRadius: 3, backgroundColor: t.bg, overflow: "hidden" },
    barFill: { height: 6, borderRadius: 3, backgroundColor: t.primary },

    signOut: {
      marginTop: 24,
      backgroundColor: t.dangerLight,
      borderRadius: 14,
      padding: 14,
      alignItems: "center",
    },
    signOutText: { color: t.danger, fontWeight: "700", fontSize: 15 },

    mOverlay: { flex: 1, backgroundColor: t.scrim, justifyContent: "center", padding: 24 },
    mSheet: { backgroundColor: t.bg, borderRadius: 20, padding: 20, gap: 14 },
    mTitle: { fontSize: 17, fontWeight: "700", color: t.text },
    mInput: {
      backgroundColor: t.surface,
      borderRadius: 12,
      padding: 12,
      fontSize: 16,
      color: t.text,
      borderWidth: 1.5,
      borderColor: t.primary,
    },
    mActions: { flexDirection: "row", gap: 10 },
    mCancel: {
      flex: 1,
      borderRadius: 12,
      borderWidth: 1,
      borderColor: t.border,
      padding: 12,
      alignItems: "center",
    },
    mCancelText: { fontSize: 15, color: t.textSecondary, fontWeight: "600" },
    mSave: { flex: 1, borderRadius: 12, backgroundColor: t.primary, padding: 12, alignItems: "center" },
    mSaveText: { fontSize: 15, color: "#fff", fontWeight: "700" },
  });
}
