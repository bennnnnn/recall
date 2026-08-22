import { StyleSheet, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
};

export function LessonTypedAnswer({ value, onChange, onSubmit, disabled = false }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = makeStyles(theme);

  return (
    <View style={s.wrap}>
      <TextInput
        value={value}
        onChangeText={onChange}
        placeholder={t("lesson.type_placeholder")}
        placeholderTextColor={theme.textTertiary}
        editable={!disabled}
        multiline
        style={s.input}
        accessibilityLabel={t("lesson.type_placeholder")}
        onSubmitEditing={onSubmit}
      />
      <Button
        title={t("lesson.send_answer")}
        onPress={onSubmit}
        disabled={disabled || !value.trim()}
      />
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: { gap: Space.sm },
    input: {
      ...Type.body,
      minHeight: 88,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      backgroundColor: theme.surface,
      borderRadius: 14,
      padding: Space.md,
      color: theme.text,
      textAlignVertical: "top",
    },
  });
}
