import { useMemo, useRef, useState } from "react";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { SettingsFieldSheet } from "@/components/settings/SettingsFieldSheet";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { getDisplayName, sanitizeDisplayName } from "@/lib/profile";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export function SettingsProfileName() {
  const { user, updateUser } = useAuth();
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const theme = useTheme();
  const styles = useMemo(() => makeStyles(theme), [theme]);
  const [editName, setEditName] = useState(false);
  const [fieldText, setFieldText] = useState("");
  const [fieldSaving, setFieldSaving] = useState(false);
  const fieldSavingRef = useRef(false);

  const openName = () => {
    if (!user) return;
    setFieldText(user.name ?? "");
    setEditName(true);
  };

  const saveName = async () => {
    if (fieldSavingRef.current || !user) return;
    const name = sanitizeDisplayName(fieldText);
    if (!name) {
      if (fieldText.trim()) Alert.alert(t("common.error"), t("settings.name_invalid"));
      return;
    }
    if (name === user.name) {
      setEditName(false);
      return;
    }
    fieldSavingRef.current = true;
    setFieldSaving(true);
    try {
      await updateUser({ name });
      setEditName(false);
    } catch {
      if (feedback) feedback.error(t("common.error"));
      else Alert.alert(t("common.error"), t("common.error"));
    } finally {
      fieldSavingRef.current = false;
      setFieldSaving(false);
    }
  };

  const displayName = getDisplayName(user?.name, t("common.you"));

  return (
    <>
      <Pressable
        style={({ pressed }) => [styles.nameButton, pressed && styles.pressed]}
        onPress={openName}
        accessibilityRole="button"
        accessibilityLabel={t("settings.your_name")}
        accessibilityValue={{ text: displayName }}
      >
        <Text style={styles.name}>{displayName}</Text>
        <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          <Icon name="pencil-outline" size={16} color={theme.textSecondary} />
        </View>
      </Pressable>

      <SettingsFieldSheet
        visible={editName}
        title={t("settings.your_name")}
        value={fieldText}
        onChangeText={setFieldText}
        onClose={() => setEditName(false)}
        onSave={() => void saveName()}
        saving={fieldSaving}
        maxLength={80}
      />
    </>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    nameButton: {
      alignSelf: "center",
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      maxWidth: "100%",
      minHeight: Space.minTouch,
      marginTop: Space.md,
      paddingHorizontal: Space.md,
      gap: Space.xs,
    },
    name: {
      ...Type.h1,
      fontWeight: "600",
      color: theme.text,
      textAlign: "center",
      flexShrink: 1,
    },
    pressed: { opacity: 0.65 },
  });
}
