import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { C } from "@/constants/Colors";
import { api, Suggestion } from "@/lib/api";

type Props = {
  token: string;
  onSelect: (text: string) => void;
};

export function SuggestionChips({ token, onSelect }: Props) {
  const { t } = useTranslation();
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api
      .listSuggestions(token)
      .then((items) => {
        if (!cancelled) setSuggestions(items);
      })
      .catch(() => {
        // Silently ignore — suggestions are best-effort.
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (loading || suggestions.length === 0) return null;

  const dismiss = (id: string) => {
    setSuggestions((prev) => prev.filter((s) => s.id !== id));
    api.dismissSuggestion(token, id).catch(() => {
      // Best-effort dismiss — ignore network errors.
    });
  };

  return (
    <View style={s.wrap}>
      <Text style={s.hint}>{t("chat.suggestions")}</Text>
      <View style={s.row}>
        {suggestions.map((sg) => (
          <Pressable
            key={sg.id}
            style={s.chip}
            onPress={() => {
              onSelect(sg.text);
              dismiss(sg.id);
            }}
          >
            <Text style={s.chipText} numberOfLines={1}>
              {sg.text}
            </Text>
            <Pressable onPress={() => dismiss(sg.id)} hitSlop={8}>
              <Ionicons name="close" size={14} color={C.textTertiary} />
            </Pressable>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { paddingHorizontal: 16, paddingBottom: 10, gap: 6 },
  hint: { fontSize: 11, fontWeight: "700", color: C.textTertiary, textTransform: "uppercase", letterSpacing: 0.8 },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: C.primaryLight,
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 8,
    maxWidth: "100%",
    borderWidth: 1,
    borderColor: C.primary + "30",
  },
  chipText: { fontSize: 14, fontWeight: "500", color: C.primary, flexShrink: 1 },
});
