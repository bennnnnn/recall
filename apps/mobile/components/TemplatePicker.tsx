import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { api, Template } from "@/lib/api";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  token: string;
  /** Prefill the composer with the chosen template's content (does not send). */
  onSelect: (content: string) => void;
  /** How many templates to show. */
  limit?: number;
};

export function TemplatePicker({ token, onSelect, limit = 6 }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [templates, setTemplates] = useState<Template[]>([]);

  useEffect(() => {
    let cancelled = false;
    api
      .listTemplates(token)
      .then((items) => {
        if (!cancelled) setTemplates(items);
      })
      .catch(() => {
        // Best-effort — templates are a convenience, never block the screen.
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (templates.length === 0) return null;

  return (
    <View style={s.wrap}>
      <Text style={s.hint}>{t("chat.templates")}</Text>
      <View style={s.row}>
        {templates.slice(0, limit).map((tpl) => (
          <Pressable key={tpl.id} style={s.card} onPress={() => onSelect(tpl.content)}>
            <Text style={s.cardTitle} numberOfLines={1}>
              {tpl.title}
            </Text>
            {tpl.category ? (
              <Text style={s.cardCat} numberOfLines={1}>
                {tpl.category}
              </Text>
            ) : null}
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: { width: "100%", paddingHorizontal: 8, gap: 8, marginTop: 20 },
    hint: {
      fontSize: 11,
      fontWeight: "700",
      color: t.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.8,
      textAlign: "center",
    },
    row: { flexDirection: "row", flexWrap: "wrap", gap: 8, justifyContent: "center" },
    card: {
      backgroundColor: t.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      borderRadius: 14,
      paddingHorizontal: 14,
      paddingVertical: 10,
      maxWidth: "46%",
    },
    cardTitle: { fontSize: 14, fontWeight: "600", color: t.text },
    cardCat: { fontSize: 11, color: t.textTertiary, marginTop: 2, textTransform: "capitalize" },
  });
}
