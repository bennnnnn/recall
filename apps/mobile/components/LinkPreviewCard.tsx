import { useEffect, useMemo, useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { fetchLinkPreview, LinkPreview } from "@/lib/linkPreview";
import { Theme, useTheme } from "@/lib/theme";

type Props = { url: string };

export function LinkPreviewCard({ url }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [preview, setPreview] = useState<LinkPreview | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchLinkPreview(url)
      .then((data) => {
        if (!cancelled) setPreview(data);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [url]);

  const open = () => {
    Linking.openURL(url).catch(() => {});
  };

  if (failed) {
    return (
      <Pressable style={s.wrap} onPress={open}>
        <Ionicons name="link-outline" size={16} color={theme.primary} />
        <Text style={s.url} numberOfLines={2}>
          {url}
        </Text>
      </Pressable>
    );
  }

  if (!preview) {
    return (
      <View style={[s.wrap, s.loading]}>
        <Text style={s.loadingText}>{t("chat.link_preview_loading")}</Text>
      </View>
    );
  }

  return (
    <Pressable style={s.wrap} onPress={open}>
      <Text style={s.title} numberOfLines={2}>
        {preview.title || preview.url}
      </Text>
      {preview.description ? (
        <Text style={s.desc} numberOfLines={3}>
          {preview.description}
        </Text>
      ) : null}
      <Text style={s.domain}>{preview.domain}</Text>
    </Pressable>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: {
      alignSelf: "stretch",
      borderRadius: 12,
      borderWidth: 1,
      borderColor: theme.border,
      backgroundColor: theme.surface,
      paddingHorizontal: 12,
      paddingVertical: 10,
      marginVertical: 8,
      gap: 4,
    },
    loading: { opacity: 0.7 },
    loadingText: { fontSize: 14, color: theme.textSecondary },
    title: { fontSize: 15, fontWeight: "700", color: theme.text },
    desc: { fontSize: 14, lineHeight: 20, color: theme.textSecondary },
    domain: { fontSize: 12, color: theme.primary, marginTop: 2 },
    url: { flex: 1, fontSize: 14, color: theme.primary },
  });
}
