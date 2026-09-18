import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { tap } from "@/lib/haptics";
import { Space } from "@/lib/space";
import { useTheme, type Theme } from "@/lib/theme";
import { Type } from "@/lib/type";

/**
 * Thin persistent strip above the composer while offline. The send button
 * already dims, but without this there is no signal *why* until a send is
 * attempted. Dismissal lasts for the current offline stretch only — the
 * strip returns on the next connectivity drop.
 */
export function ChatOfflineStrip({
  offline,
  bottom,
}: {
  offline: boolean;
  bottom: number;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (offline) setDismissed(false);
  }, [offline]);

  if (!offline || dismissed) return null;

  return (
    <View style={[s.wrap, { bottom }]}>
      <Icon name="cloud-offline-outline" size={14} color={theme.textSecondary} />
      <Text style={s.text} numberOfLines={1}>
        {t("chat.offline_body")}
      </Text>
      <Pressable
        onPress={() => {
          tap();
          setDismissed(true);
        }}
        style={s.close}
        accessibilityRole="button"
        accessibilityLabel={t("common.close")}
      >
        <Icon name="close" size={12} color={theme.textTertiary} />
      </Pressable>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: {
      position: "absolute",
      left: Space.lg,
      right: Space.lg,
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      paddingVertical: Space.xs,
      paddingHorizontal: Space.sm,
      borderRadius: 10,
      backgroundColor: theme.surfaceAlt,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    text: {
      ...Type.caption,
      color: theme.textSecondary,
      flex: 1,
    },
    close: {
      width: Space.minTouch,
      height: Space.minTouch,
      alignItems: "center",
      justifyContent: "center",
      marginVertical: -Space.sm,
      marginRight: -Space.xs,
    },
  });
}
