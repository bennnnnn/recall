import { useMemo } from "react";
import { StyleSheet, Text } from "react-native";
import { useTranslation } from "react-i18next";

import { EditableProfileAvatar } from "@/components/settings/EditableProfileAvatar";
import { SettingsProfileSheet } from "@/components/settings/SettingsProfileSheet";
import { useAuth } from "@/contexts/AuthContext";
import { useProfileEditor } from "@/hooks/useProfileEditor";
import { getDisplayName } from "@/lib/profile";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export function SettingsProfile() {
  const { user, token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const editor = useProfileEditor();

  return (
    <>
      <EditableProfileAvatar
        name={user?.name ?? null}
        uri={user?.avatar_url}
        token={token}
        size={88}
        icon="pencil-outline"
        label={t("settings.edit_profile")}
        onPress={editor.open}
      />
      <Text style={s.name} accessibilityRole="header">
        {getDisplayName(user?.name, t("common.you"))}
      </Text>
      <SettingsProfileSheet editor={editor} avatarUri={user?.avatar_url} token={token} />
    </>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    name: {
      ...Type.h1,
      fontWeight: "600",
      color: theme.text,
      textAlign: "center",
      marginTop: Space.md,
      paddingHorizontal: Space.md,
    },
  });
}
