import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Sheet } from "@/ui/overlay/Sheet";
import { SegmentedControl } from "@/ui/controls/SegmentedControl";
import { ListRow } from "@/ui/list/ListRow";
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

  return (
    <Sheet
      visible={visible}
      onClose={onClose}
      variant="bottom"
      withHandle
      floating
      minBottomPadding={12}
      contentContainerStyle={s.panel}
    >
      <Text style={s.title}>{t("lesson.menu")}</Text>
      <ListRow
        appearance="plain"
        title={t("lesson.effect_sound")}
        switchValue={prefs.effectSound}
        onSwitchChange={(effectSound) => onChange({ effectSound })}
        style={s.row}
      />
      <ListRow
        appearance="plain"
        title={t("lesson.read_words")}
        switchValue={prefs.readWords}
        onSwitchChange={(readWords) => onChange({ readWords })}
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
    panel: { backgroundColor: theme.elevated },
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
