import { useMemo } from "react";
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
import { useTranslation } from "react-i18next";

import { useTemplates } from "@/hooks/useTemplates";
import type { Template } from "@/lib/api";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  visible: boolean;
  onClose: () => void;
  onSelect: (content: string) => void;
};

export function TemplatesSheet({ visible, onClose, onSelect }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { templates, loading, error, refresh } = useTemplates(visible);

  const builtin = templates.filter((item) => item.is_builtin);
  const custom = templates.filter((item) => !item.is_builtin);

  const pick = (template: Template) => {
    onSelect(template.content);
    onClose();
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <Pressable style={s.backdrop} onPress={onClose} accessibilityLabel={t("common.close")} />
      <View style={s.sheet}>
        <View style={s.handle} />
        <Text style={s.title}>{t("templates.title")}</Text>

        {loading && templates.length === 0 ? (
          <View style={s.center}>
            <ActivityIndicator color={theme.primary} />
          </View>
        ) : error ? (
          <View style={s.center}>
            <Text style={s.errorText}>{t("common.error")}</Text>
            <Pressable style={s.retryBtn} onPress={() => void refresh()}>
              <Text style={s.retryText}>{t("common.retry")}</Text>
            </Pressable>
          </View>
        ) : templates.length === 0 ? (
          <View style={s.center}>
            <Text style={s.emptyText}>{t("templates.empty")}</Text>
          </View>
        ) : (
          <ScrollView style={s.scroll} contentContainerStyle={s.scrollContent}>
            {builtin.length > 0 ? (
              <TemplateSection
                label={t("templates.builtin")}
                items={builtin}
                onPick={pick}
                styles={s}
                theme={theme}
                useLabel={t("templates.use")}
              />
            ) : null}
            {custom.length > 0 ? (
              <TemplateSection
                label={t("templates.custom")}
                items={custom}
                onPick={pick}
                styles={s}
                theme={theme}
                useLabel={t("templates.use")}
              />
            ) : null}
          </ScrollView>
        )}
      </View>
    </Modal>
  );
}

function TemplateSection({
  label,
  items,
  onPick,
  styles: s,
  theme,
  useLabel,
}: {
  label: string;
  items: Template[];
  onPick: (template: Template) => void;
  styles: ReturnType<typeof makeStyles>;
  theme: Theme;
  useLabel: string;
}) {
  return (
    <View style={s.section}>
      <Text style={s.sectionLabel}>{label}</Text>
      {items.map((item) => (
        <Pressable
          key={item.id}
          style={s.row}
          onPress={() => onPick(item)}
          accessibilityRole="button"
          accessibilityLabel={item.title}
        >
          <Ionicons name="document-text-outline" size={18} color={theme.primary} />
          <View style={s.rowMain}>
            <Text style={s.rowTitle} numberOfLines={1}>
              {item.title}
            </Text>
            <Text style={s.rowPreview} numberOfLines={2}>
              {item.content}
            </Text>
          </View>
          <Text style={s.useLabel}>{useLabel}</Text>
        </Pressable>
      ))}
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    backdrop: {
      flex: 1,
      backgroundColor: "rgba(0,0,0,0.35)",
    },
    sheet: {
      maxHeight: "72%",
      backgroundColor: theme.bg,
      borderTopLeftRadius: 20,
      borderTopRightRadius: 20,
      paddingBottom: 24,
    },
    handle: {
      alignSelf: "center",
      width: 36,
      height: 4,
      borderRadius: 2,
      backgroundColor: theme.border,
      marginTop: 10,
      marginBottom: 8,
    },
    title: {
      fontSize: 18,
      fontWeight: "700",
      color: theme.text,
      textAlign: "center",
      marginBottom: 12,
    },
    scroll: { flexGrow: 0 },
    scrollContent: { paddingHorizontal: 16, paddingBottom: 8, gap: 16 },
    center: { paddingVertical: 32, alignItems: "center", gap: 12 },
    emptyText: { fontSize: 15, color: theme.textSecondary },
    errorText: { fontSize: 15, color: theme.danger },
    retryBtn: {
      paddingHorizontal: 16,
      paddingVertical: 8,
      borderRadius: 999,
      backgroundColor: theme.surface,
    },
    retryText: { fontSize: 14, fontWeight: "600", color: theme.primary },
    section: { gap: 8 },
    sectionLabel: {
      fontSize: 13,
      fontWeight: "700",
      color: theme.textSecondary,
      textTransform: "uppercase",
      letterSpacing: 0.4,
    },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      padding: 12,
      borderRadius: 14,
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    rowMain: { flex: 1, gap: 2 },
    rowTitle: { fontSize: 15, fontWeight: "600", color: theme.text },
    rowPreview: { fontSize: 13, lineHeight: 18, color: theme.textSecondary },
    useLabel: { fontSize: 12, fontWeight: "700", color: theme.primary },
  });
}
