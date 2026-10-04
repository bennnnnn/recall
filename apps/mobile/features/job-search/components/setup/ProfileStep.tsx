import { View } from "react-native";
import { useTranslation } from "react-i18next";

import type { JobSearchExperience } from "@/lib/api";

import {
  EXPERIENCE_VALUES,
  FieldLabel,
  SelectChip,
  useSetupStyles,
} from "./setupShared";
import { TextField } from "@/ui/controls/TextField";

type Props = {
  levels: JobSearchExperience[];
  salary: string;
  salaryCurrency: string | null;
  salaryError: string | null;
  busy: boolean;
  onExperiencePress: (level: JobSearchExperience) => void;
  onSalaryChange: (salary: string) => void;
};

export function ProfileStep({
  levels,
  salary,
  salaryCurrency,
  salaryError,
  busy,
  onExperiencePress,
  onSalaryChange,
}: Props) {
  const { t } = useTranslation();
  const s = useSetupStyles();

  return (
    <>
      <View style={s.fieldGroup}>
        <FieldLabel>{t("my_job.experience_label")}</FieldLabel>
        <View style={s.chipRow}>
          {EXPERIENCE_VALUES.map((level) => (
            <SelectChip
              key={level}
              value={level}
              label={t(`my_job.level_${level}`)}
              selected={levels.includes(level)}
              onPress={onExperiencePress}
              disabled={busy}
            />
          ))}
        </View>
      </View>

      <View style={s.twoColumnRow}>
        <View style={s.flexField}>
          <FieldLabel>{`${t("my_job.salary_label")}${salaryCurrency ? ` (${salaryCurrency})` : ""}`}</FieldLabel>
          <TextField
            value={salary}
            onChangeText={onSalaryChange}
            placeholder="100000"
            accessibilityLabel={t("my_job.salary_label")}
            editable={!busy}
            keyboardType="number-pad"
            error={salaryError}
          />
        </View>
      </View>

    </>
  );
}
