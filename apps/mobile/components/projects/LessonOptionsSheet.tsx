import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { makeActionSheetPanelStyle } from "@/components/ActionSheetRow";
import { SwitchRow } from "@/components/SwitchRow";
import type { LessonFontSize, LessonPrefs } from "@/lib/projects/lessonPrefs";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  visible: boolean;
  prefs: LessonPrefs;
  onClose: () => void;
  onChange: (patch: Partial<LessonPrefs>) => void;
};

const FONT_SIZES: LessonFontSize[] = ["small", "medium", "large"];

export function LessonOptionsSheet({ visible, prefs, onClose, onChange }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = makeStyles(theme);
  const panelStyle = makeActionSheetPanelStyle(theme);

  return (
    <AppSheet
      visible={visible}
      onClose={onClose}
      variant="bottom"
      withHandle
      floating
      minBottomPadding={12}
      contentContainerStyle={panelStyle}
    >
      <Text style={s.title}>{t("lesson.menu")}</Text>
      <SwitchRow
        label={t("lesson.effect_sound")}
        value={prefs.effectSound}
        onValueChange={(effectSound) => onChange({ effectSound })}
        style={s.row}
      />
      <SwitchRow
        label={t("lesson.read_words")}
        value={prefs.readWords}
        onValueChange={(readWords) => onChange({ readWords })}
        style={s.row}
      />
      <Text style={s.fontLabel}>{t("lesson.font_size")}</Text>
      <View style={s.fonts}>
        {FONT_SIZES.map((size) => {
          const selected = prefs.fontSize === size;
          return (
            <Pressable
              key={size}
              style={[s.fontChip, selected && s.fontChipOn]}
              accessibilityRole="button"
              accessibilityState={{ selected }}
              accessibilityLabel={t(`lesson.font_${size}`)}
              onPress={() => onChange({ fontSize: size })}
            >
              <Text style={[s.fontChipText, selected && s.fontChipTextOn]}>
                {t(`lesson.font_${size}`)}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </AppSheet>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    title: {
      ...Type.caption,
      fontWeight: "600",
      color: theme.textSecondary,
      textAlign: "center",
      paddingTop: Space.xs,
      paddingBottom: Space.sm,
    },
    row: {
      paddingHorizontal: 18,
      paddingVertical: 14,
    },
    fontLabel: {
      ...Type.caption,
      fontWeight: "600",
      color: theme.textSecondary,
      paddingHorizontal: 18,
      paddingTop: Space.sm,
      paddingBottom: Space.xs,
    },
    fonts: {
      flexDirection: "row",
      gap: Space.xs,
      paddingHorizontal: 18,
      paddingBottom: Space.md,
    },
    fontChip: {
      flex: 1,
      minHeight: Space.minTouch,
      borderRadius: 12,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: theme.surfaceAlt,
    },
    fontChipOn: {
      backgroundColor: theme.primaryLight,
    },
    fontChipText: {
      ...Type.label,
      color: theme.text,
    },
    fontChipTextOn: {
      color: theme.primary,
      fontWeight: "700",
    },
  });
}
