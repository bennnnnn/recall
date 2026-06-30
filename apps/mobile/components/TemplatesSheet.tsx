import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { api, Template } from "@/lib/api";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  visible: boolean;
  token: string | null;
  onClose: () => void;
  onSelect: (content: string) => void;
};

export function TemplatesSheet({ visible, token, onClose, onSelect }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [loading, setLoading] = useState(false);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    if (!token) {
      setTemplates([]);
      return;
    }
    setLoading(true);
    setError(false);
    try {
      setTemplates(await api.listTemplates(token));
    } catch {
      setError(true);
      setTemplates([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (visible) void load();
  }, [visible, load]);

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <View style={[s.root, { paddingTop: insets.top + 8, paddingBottom: insets.bottom + 8 }]}>
        <View style={s.header}>
          <Text style={s.title}>{t("templates.title")}</Text>
          <Pressable onPress={onClose} hitSlop={12} accessibilityRole="button">
            <Ionicons name="close" size={24} color={theme.text} />
          </Pressable>
        </View>

        {loading ? (
          <View style={s.center}>
            <ActivityIndicator color={theme.primary} />
          </View>
        ) : error ? (
          <View style={s.center}>
            <Text style={s.empty}>{t("common.error")}</Text>
            <Pressable onPress={() => void load()}>
              <Text style={s.retry}>{t("common.retry")}</Text>
            </Pressable>
          </View>
        ) : templates.length === 0 ? (
          <View style={s.center}>
            <Text style={s.empty}>{t("templates.empty")}</Text>
          </View>
        ) : (
          <ScrollView contentContainerStyle={s.list}>
            {templates.map((item) => (
              <Pressable
                key={item.id}
                style={s.row}
                onPress={() => {
                  onSelect(item.content);
                  onClose();
                }}
              >
                <View style={s.rowMain}>
                  <Text style={s.rowTitle} numberOfLines={1}>
                    {item.title}
                  </Text>
                  {item.is_builtin ? (
                    <Text style={s.badge}>{t("templates.builtin")}</Text>
                  ) : null}
                  <Text style={s.rowPreview} numberOfLines={2}>
                    {item.content}
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color={theme.textTertiary} />
              </Pressable>
            ))}
          </ScrollView>
        )}
      </View>
    </Modal>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: theme.bg },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: 16,
      paddingBottom: 12,
    },
    title: { fontSize: 20, fontWeight: "700", color: theme.text },
    center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
    empty: { fontSize: 15, color: theme.textSecondary, textAlign: "center" },
    retry: { marginTop: 12, fontSize: 15, fontWeight: "600", color: theme.primary },
    list: { paddingHorizontal: 16, paddingBottom: 24 },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      paddingVertical: 14,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: theme.border,
    },
    rowMain: { flex: 1, gap: 4 },
    rowTitle: { fontSize: 16, fontWeight: "600", color: theme.text },
    badge: {
      alignSelf: "flex-start",
      fontSize: 11,
      fontWeight: "700",
      color: theme.primary,
      textTransform: "uppercase",
    },
    rowPreview: { fontSize: 14, lineHeight: 20, color: theme.textSecondary },
  });
}
