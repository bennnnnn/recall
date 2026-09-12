import { useMemo } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { EditableProfileAvatar } from "@/components/settings/EditableProfileAvatar";
import { type useProfileEditor } from "@/hooks/useProfileEditor";
import { Space } from "@/lib/space";
import { type Theme, useTheme, withAlpha } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  editor: ReturnType<typeof useProfileEditor>;
  avatarUri?: string | null;
  token: string | null;
};

export function SettingsProfileSheet({ editor, avatarUri, token }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const busy = editor.saving || editor.picking;

  return (
    <AppSheet
      visible={editor.visible}
      onClose={editor.close}
      variant="bottom"
      keyboardAvoiding
      handleColor={theme.textSecondary}
      backdropDismiss={!busy}
      backdropColor={withAlpha(theme.bg, 0.35)}
      contentContainerStyle={s.sheet}
    >
      <View style={s.body} testID="settings-profile-sheet">
        <EditableProfileAvatar
          name={editor.name}
          uri={editor.photo?.localUri ?? avatarUri}
          token={token}
          size={144}
          icon="camera-outline"
          label={t("settings.change_photo")}
          onPress={() => void editor.choosePhoto()}
          disabled={busy}
          busy={editor.picking}
        />
        <View style={s.nameField}>
          <Text style={s.nameLabel} accessible={false}>{t("settings.name_label")}</Text>
          <TextInput
            style={s.nameInput}
            accessibilityLabel={t("settings.name_label")}
            value={editor.name}
            onChangeText={editor.setName}
            editable={!busy}
            maxLength={80}
            autoCapitalize="words"
            autoCorrect={false}
            returnKeyType="done"
            onSubmitEditing={() => void editor.save()}
          />
        </View>
        {editor.error ? <Text style={s.error} accessibilityRole="alert">{editor.error}</Text> : null}
        <Pressable
          onPress={() => void editor.save()}
          disabled={busy}
          accessibilityRole="button"
          accessibilityLabel={t("settings.save_profile")}
          accessibilityState={{ disabled: busy, busy: editor.saving }}
          style={({ pressed }) => [s.save, pressed && s.pressed, busy && s.disabled]}
        >
          {editor.saving ? <ActivityIndicator color={theme.bg} /> : (
            <Text style={s.saveText}>{t("settings.save_profile")}</Text>
          )}
        </Pressable>
        <Pressable
          onPress={editor.close}
          disabled={busy}
          accessibilityRole="button"
          accessibilityState={{ disabled: busy }}
          style={({ pressed }) => [s.cancel, pressed && s.pressed]}
        >
          <Text style={s.cancelText}>{t("settings.cancel")}</Text>
        </Pressable>
      </View>
    </AppSheet>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    sheet: {
      backgroundColor: theme.surfaceAlt,
      borderTopLeftRadius: 32,
      borderTopRightRadius: 32,
    },
    body: { paddingHorizontal: Space.gutter, paddingTop: Space.xl, paddingBottom: Space.lg },
    nameField: {
      marginTop: Space.xl,
      borderWidth: 1.5,
      borderColor: theme.border,
      borderRadius: 36,
      minHeight: 72,
      justifyContent: "center",
    },
    nameLabel: {
      ...Type.body,
      color: theme.textSecondary,
      position: "absolute",
      top: -14,
      left: Space.md,
      paddingHorizontal: Space.xs,
      backgroundColor: theme.surfaceAlt,
    },
    nameInput: {
      ...Type.h1,
      fontWeight: "400",
      color: theme.text,
      paddingHorizontal: Space.lg,
      paddingVertical: Space.md,
    },
    error: { ...Type.secondary, color: theme.danger, marginTop: Space.md, textAlign: "center" },
    save: {
      alignSelf: "center",
      marginTop: Space.xl,
      minWidth: 180,
      minHeight: 64,
      paddingHorizontal: Space.lg,
      paddingVertical: Space.md,
      borderRadius: 32,
      backgroundColor: theme.text,
      alignItems: "center",
      justifyContent: "center",
    },
    saveText: { ...Type.h1, color: theme.bg },
    cancel: { alignSelf: "center", marginTop: Space.sm, minHeight: 48, justifyContent: "center", paddingHorizontal: Space.lg },
    cancelText: { ...Type.body, fontSize: 18, fontWeight: "600", color: theme.text },
    pressed: { opacity: 0.65 },
    disabled: { opacity: 0.55 },
  });
}
