import { Link, Stack } from "expo-router";
import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";

export default function NotFoundScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <>
      <Stack.Screen options={{ title: t("common.error") }} />
      <View style={s.container}>
        <Text style={s.title}>{t("common.not_found_title")}</Text>
        <Link href="/" asChild>
          <Pressable style={s.link}>
            <Text style={s.linkText}>{t("common.not_found_home")}</Text>
          </Pressable>
        </Link>
      </View>
    </>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    container: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      padding: 20,
      backgroundColor: theme.bg,
    },
    title: {
      fontSize: 20,
      fontWeight: "700",
      color: theme.text,
      textAlign: "center",
    },
    link: {
      marginTop: 15,
      paddingVertical: 15,
    },
    linkText: {
      fontSize: 15,
      fontWeight: "600",
      color: theme.primary,
    },
  });
}
