import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/ui/icons/Icon";
import { useTranslation } from "react-i18next";

import { fetchLinkPreview, LinkPreview } from "@/lib/linkPreview";
import { openAllowedUrl } from "@/lib/linkSchemePolicy";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { IconSize } from "@/ui/icons/sizes";

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
    void openAllowedUrl(url);
  };

  if (failed) {
    return (
      <Pressable
        style={s.wrap}
        onPress={open}
        accessibilityRole="link"
        accessibilityLabel={url}
      >
        <Icon name="link" size={IconSize.xs} color={theme.primary} />
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
    <Pressable
      style={s.wrap}
      onPress={open}
      accessibilityRole="link"
      accessibilityLabel={preview.title || preview.url}
    >
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
      borderRadius: Radius.md,
      borderWidth: 1,
      borderColor: theme.border,
      backgroundColor: theme.surface,
      paddingHorizontal: Space.sm,
      paddingVertical: 10,
      marginVertical: Space.xs,
      gap: Space.xxs,
    },
    loading: { opacity: 0.7 },
    loadingText: { ...Type.secondary, color: theme.textSecondary },
    title: { ...Type.callout, ...Weight.bold, color: theme.text },
    desc: { ...Type.secondary, lineHeight: 20, color: theme.textSecondary },
    domain: { ...Type.meta, color: theme.primary, marginTop: 2 },
    url: { flex: 1, ...Type.secondary, color: theme.primary },
  });
}
