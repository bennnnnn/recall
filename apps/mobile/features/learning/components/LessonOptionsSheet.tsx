import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Sheet } from "@/ui/overlay/Sheet";
import { makeActionSheetPanelStyle } from "@/components/ActionSheetRow";
import { SegmentedControl } from "@/ui/controls/SegmentedControl";
import { SwitchRow } from "@/ui/controls/SwitchRow";
import type { LessonFontSize, LessonPrefs } from "@/features/learning/model/lessonPrefs";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

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
    <Sheet
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
        <SegmentedControl
          segments={FONT_SIZES.map((size) => ({ key: size, label: t(`lesson.font_${size}`) }))}
          value={prefs.fontSize}
          onChange={(fontSize) => onChange({ fontSize })}
          accessibilityLabel={t("lesson.font_size")}
          testID="lesson-font-size"
        />
      </View>
    </Sheet>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    title: {
      ...Type.caption,
      ...Weight.semibold,
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
      ...Weight.semibold,
      color: theme.textSecondary,
      paddingHorizontal: 18,
      paddingTop: Space.sm,
      paddingBottom: Space.xs,
    },
    fonts: {
      paddingHorizontal: 18,
      paddingBottom: Space.md,
    },
  });
}
