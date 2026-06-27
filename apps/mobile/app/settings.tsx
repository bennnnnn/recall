import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
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
import { C } from "@/constants/Colors";
import { useAuth } from "@/contexts/AuthContext";
import { api, Usage } from "@/lib/api";

const MODELS = ["auto", "free-chat", "smart-chat"] as const;
const STYLES = ["short", "balanced", "detailed"] as const;
const MODEL_LABEL: Record<string, string> = {
  auto: "Auto",
  "free-chat": "Flash",
  "smart-chat": "Pro",
};

const LANG_LABEL: Record<string, string> = {
  en: "English",
  es: "Español",
  fr: "Français",
  am: "አማርኛ",
};

export default function SettingsScreen() {
  const { token, user, signOut, refreshUser, updateUser } = useAuth();
  const { t } = useTranslation();
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
    Promise.all([
      refreshUser(),
      api.todayUsage(token),
      api.listMemories(token),
    ])
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

  // Sync customText when user data loads/changes from server, but only if
  // there's no pending local edit (the user isn't actively typing).
  const customDirtyRef = useRef(false);
  useEffect(() => {
    if (!customDirtyRef.current) {
      setCustomText(user?.custom_instructions ?? "");
    }
  }, [user?.custom_instructions]);

  // Clean up debounce timer on unmount.
  useEffect(() => {
    return () => {
      if (customSaveTimer.current) clearTimeout(customSaveTimer.current);
    };
  }, []);

  // Debounced auto-save for custom instructions.
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

  const patch = async (fields: Parameters<typeof updateUser>[0]) => {
    setSaving(true);
    try {
      await updateUser(fields);
    } finally {
      setSaving(false);
    }
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
    Alert.alert(
      t("delete.title"),
      t("delete.message"),
      [
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
      ],
    );
  };

  if (!token) return <Redirect href="/login" />;

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator color={C.primary} />
      </View>
    );
  }

  return (
    <View style={s.root}>
      <View style={s.card}>
        <View style={s.row}>
          <Avatar name={user?.name ?? null} uri={user?.avatar_url} size={44} />
          <View style={[s.rowBody, { marginLeft: 12 }]}>
            <Text style={s.value}>{user?.name ?? t("common.you")}</Text>
            <Text style={s.meta}>{user?.email}</Text>
          </View>
          <Pressable
            hitSlop={8}
            onPress={() => {
              setNameText(user?.name ?? "");
              setEditNameVisible(true);
            }}
          >
            <Ionicons name="pencil-outline" size={18} color={C.primary} />
          </Pressable>
        </View>
      </View>

      <View style={s.card}>
        <Text style={s.label}>{t("settings.model")}</Text>
        <View style={s.chipRow}>
          {MODELS.map((m) => (
            <Pressable
              key={m}
              disabled={saving}
              style={[s.chip, user?.default_model === m && s.chipActive]}
              onPress={() => patch({ default_model: m })}
            >
              <Text
                style={
                  user?.default_model === m ? s.chipTextActive : s.chipText
                }
              >
                {MODEL_LABEL[m]}
              </Text>
            </Pressable>
          ))}
        </View>
        <Text style={[s.label, { marginTop: 12 }]}>{t("settings.style")}</Text>
        <View style={s.chipRow}>
          {STYLES.map((st) => (
            <Pressable
              key={st}
              disabled={saving}
              style={[s.chip, user?.response_style === st && s.chipActive]}
              onPress={() => patch({ response_style: st })}
            >
              <Text
                style={
                  user?.response_style === st ? s.chipTextActive : s.chipText
                }
              >
                {st}
              </Text>
            </Pressable>
          ))}
        </View>
      </View>

      <View style={s.card}>
        <Text style={s.label}>{t("settings.custom_instructions")}</Text>
        <Text style={[s.meta, { marginBottom: 10 }]}>
          {t("settings.custom_instructions_hint")}
        </Text>
        <View style={s.customInputWrap}>
          <TextInput
            style={s.customInput}
            placeholder={t("settings.custom_instructions_placeholder")}
            placeholderTextColor={C.textTertiary}
            value={customText}
            onChangeText={saveCustom}
            multiline
            numberOfLines={5}
            textAlignVertical="top"
            returnKeyType="default"
            blurOnSubmit
          />
          {user?.custom_instructions ? (
            <Pressable
              style={s.clearInstructions}
              onPress={() => patch({ custom_instructions: "" })}
              hitSlop={6}
            >
              <Ionicons
                name="close-circle"
                size={20}
                color={C.textTertiary}
              />
            </Pressable>
          ) : null}
        </View>
      </View>

      <View style={s.card}>
        <Text style={s.label}>{t("settings.language")}</Text>
        <View style={s.chipRow}>
          {(["en", "es", "fr", "am"] as const).map((code) => {
            return (
              <Pressable
                key={code}
                disabled={saving}
                style={[
                  s.chip,
                  user?.locale === code && s.chipActive,
                ]}
                onPress={() => patch({ locale: code })}
              >
                <Text
                  style={
                    user?.locale === code ? s.chipTextActive : s.chipText
                  }
                >
                  {LANG_LABEL[code]}
                </Text>
              </Pressable>
            );
          })}
        </View>
      </View>

      <View style={s.card}>
        <View style={s.row}>
          <View style={s.rowBody}>
            <Text style={s.label}>{t("settings.memory")}</Text>
            <Text style={s.meta}>{t("settings.memory_desc")}</Text>
          </View>
          <Switch
            value={user?.memory_enabled ?? true}
            disabled={saving}
            thumbColor={C.bg}
            trackColor={{ false: C.border, true: C.primary }}
            onValueChange={(v) => patch({ memory_enabled: v })}
          />
        </View>
        <Pressable style={s.linkRow} onPress={() => router.push("/memory")}>
          <Ionicons name="sparkles-outline" size={18} color={C.primary} />
          <View style={s.rowBody}>
            <Text style={s.linkText}>{t("settings.memory_view")}</Text>
            <Text style={s.meta}>
              {memCount > 0
                ? t("settings.memory_count", { count: memCount })
                : t("settings.memory_empty")}
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={C.textTertiary} />
        </Pressable>
      </View>

      {usage && (
        <View style={s.card}>
          <Text style={s.label}>{t("settings.free_plan")}</Text>
          <View style={s.bar}>
            <View
              style={[
                s.barFill,
                {
                  width: `${Math.min(
                    100,
                    ((usage.input_tokens + usage.output_tokens) /
                      usage.daily_limit) *
                      100,
                  )}%` as `${number}%`,
                },
              ]}
            />
          </View>
          <Text style={s.meta}>
            {usage.remaining <= 0
              ? "You've used today's free limit. Go Pro for more, or come back tomorrow."
              : `${Math.round((usage.remaining / usage.daily_limit) * 100)}% of today's free limit left`}
          </Text>
        </View>
      )}

      <View style={s.card}>
        <Pressable style={s.actionRow} onPress={doExport}>
          <Ionicons name="download-outline" size={18} color={C.primary} />
          <Text style={s.actionText}>{t("settings.export")}</Text>
          <Ionicons name="chevron-forward" size={18} color={C.textTertiary} />
        </Pressable>
        <Pressable
          style={[s.actionRow, s.actionRowBorder]}
          onPress={confirmDeleteAccount}
        >
          <Ionicons name="trash-outline" size={18} color={C.danger} />
          <Text style={[s.actionText, { color: C.danger }]}>
            {t("settings.delete")}
          </Text>
        </Pressable>
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

      <Modal
        visible={editNameVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setEditNameVisible(false)}
      >
        <Pressable style={m.overlay} onPress={() => setEditNameVisible(false)}>
          <Pressable style={m.sheet} onPress={(e) => e.stopPropagation()}>
            <Text style={m.title}>{t("settings.your_name")}</Text>
            <TextInput
              style={m.input}
              value={nameText}
              onChangeText={setNameText}
              autoFocus
              returnKeyType="done"
              onSubmitEditing={saveName}
              maxLength={80}
            />
            <View style={m.actions}>
              <Pressable
                style={m.cancel}
                onPress={() => setEditNameVisible(false)}
              >
                <Text style={m.cancelText}>{t("settings.cancel")}</Text>
              </Pressable>
              <Pressable style={m.save} onPress={saveName}>
                <Text style={m.saveText}>{t("settings.save")}</Text>
              </Pressable>
            </View>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: C.bg,
  },
  root: { flex: 1, backgroundColor: C.bg, padding: 16 },
  card: {
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 14,
    padding: 14,
    marginBottom: 12,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  rowBody: { flex: 1 },
  linkRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginTop: 14,
    paddingTop: 14,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: C.border,
  },
  linkText: { fontSize: 15, fontWeight: "600", color: C.text, marginBottom: 2 },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 4 },
  chip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: C.border,
    paddingHorizontal: 14,
    paddingVertical: 6,
  },
  chipActive: { backgroundColor: C.primary, borderColor: C.primary },
  chipText: { color: C.text, fontSize: 13 },
  chipTextActive: { color: "#fff", fontSize: 13, fontWeight: "600" },
  label: { fontSize: 13, color: C.textSecondary, marginBottom: 4 },
  value: { fontSize: 16, fontWeight: "500", color: C.text, marginBottom: 4 },
  meta: { fontSize: 13, color: C.textTertiary },
  customInputWrap: { position: "relative" },
  customInput: {
    backgroundColor: C.surface,
    borderRadius: 12,
    padding: 10,
    fontSize: 14,
    lineHeight: 20,
    color: C.text,
    borderWidth: 1,
    borderColor: C.border,
    minHeight: 100,
    maxHeight: 200,
  },
  clearInstructions: {
    position: "absolute",
    top: 8,
    right: 8,
  },
  bar: {
    height: 4,
    borderRadius: 2,
    backgroundColor: C.surface,
    marginTop: 8,
    marginBottom: 4,
    overflow: "hidden",
  },
  barFill: { height: 4, borderRadius: 2, backgroundColor: C.primary },
  signOut: {
    marginTop: 12,
    backgroundColor: "#FFF0EF",
    borderRadius: 14,
    padding: 14,
    alignItems: "center",
  },
  signOutText: { color: C.danger, fontWeight: "600", fontSize: 15 },
  actionRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 10,
  },
  actionRowBorder: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: C.border,
    marginTop: 4,
    paddingTop: 14,
  },
  actionText: { flex: 1, fontSize: 15, fontWeight: "600", color: C.text },
});

const m = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.4)",
    justifyContent: "center",
    padding: 24,
  },
  sheet: { backgroundColor: C.bg, borderRadius: 20, padding: 20, gap: 14 },
  title: { fontSize: 17, fontWeight: "700", color: C.text },
  input: {
    backgroundColor: C.surface,
    borderRadius: 12,
    padding: 12,
    fontSize: 16,
    color: C.text,
    borderWidth: 1.5,
    borderColor: C.primary,
  },
  actions: { flexDirection: "row", gap: 10 },
  cancel: {
    flex: 1,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    padding: 12,
    alignItems: "center",
  },
  cancelText: { fontSize: 15, color: C.textSecondary, fontWeight: "600" },
  save: {
    flex: 1,
    borderRadius: 12,
    backgroundColor: C.primary,
    padding: 12,
    alignItems: "center",
  },
  saveText: { fontSize: 15, color: "#fff", fontWeight: "700" },
});
