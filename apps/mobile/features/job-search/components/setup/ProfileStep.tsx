import { Pressable, Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import type { JobSearchExperience } from "@/lib/api";
import { useTheme } from "@/lib/theme";

import {
  EXPERIENCE_VALUES,
  FieldLabel,
  SelectChip,
  useSetupStyles,
} from "./setupShared";
import { IconSize } from "@/ui/icons/sizes";

type Props = {
  resumeName: string | null;
  uploadingResume: boolean;
  levels: JobSearchExperience[];
  salary: string;
  requiresSponsorship: boolean | null;
  excludedCompanies: string;
  salaryError: boolean;
  busy: boolean;
  onChooseResume: () => void;
  onRemoveResume: () => void;
  onExperiencePress: (level: JobSearchExperience) => void;
  onSalaryChange: (salary: string) => void;
  onSponsorshipChange: (value: boolean | null) => void;
  onExcludedCompaniesChange: (value: string) => void;
};

export function ProfileStep({
  resumeName,
  uploadingResume,
  levels,
  salary,
  requiresSponsorship,
  excludedCompanies,
  salaryError,
  busy,
  onChooseResume,
  onRemoveResume,
  onExperiencePress,
  onSalaryChange,
  onSponsorshipChange,
  onExcludedCompaniesChange,
}: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useSetupStyles();

  return (
    <>
      <View style={s.fieldGroup}>
        <FieldLabel>{t("my_job.resume_label")}</FieldLabel>
        <Pressable
          style={({ pressed }) => [s.resumeCard, pressed && s.pressed]}
          onPress={onChooseResume}
          disabled={busy || uploadingResume}
          accessibilityRole="button"
          accessibilityLabel={
            resumeName
              ? t("my_job.resume_replace_a11y")
              : t("my_job.resume_upload_a11y")
          }
        >
          <View style={s.resumeIcon}>
            <Icon name="file-text" size={IconSize.md} color={C.primary} />
          </View>
          <View style={s.resumeCopy}>
            <Text style={s.resumeTitle} numberOfLines={1}>
              {uploadingResume
                ? t("my_job.resume_uploading")
                : resumeName
                  ? resumeName
                  : t("my_job.resume_upload_cta")}
            </Text>
            <Text style={s.resumeMeta}>
              {resumeName
                ? t("my_job.resume_tap_replace")
                : t("my_job.resume_meta")}
            </Text>
          </View>
          <Icon name="chevron-right" size={IconSize.sm} color={C.textTertiary} />
        </Pressable>
        {resumeName ? (
          <Pressable
            style={s.removeResume}
            onPress={onRemoveResume}
            disabled={busy}
          >
            <Text style={s.removeResumeText}>{t("my_job.resume_remove")}</Text>
          </Pressable>
        ) : null}
      </View>

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
          <FieldLabel>{t("my_job.salary_label")}</FieldLabel>
          <TextInput
            style={[s.input, salaryError && s.inputError]}
            value={salary}
            onChangeText={onSalaryChange}
            placeholder="100000"
            placeholderTextColor={C.textDisabled}
            editable={!busy}
            keyboardType="number-pad"
          />
          {salaryError ? (
            <Text style={s.errorText}>{t("my_job.salary_invalid_body")}</Text>
          ) : null}
        </View>
      </View>

      <View style={s.fieldGroup}>
        <FieldLabel>{t("my_job.sponsorship_label")}</FieldLabel>
        <View style={s.chipRow}>
          {([true, false, null] as const).map((value) => (
            <SelectChip
              key={value === null ? "unsure" : String(value)}
              value={value === null ? "unsure" : String(value)}
              label={
                value === true
                  ? t("my_job.sponsorship_yes")
                  : value === false
                    ? t("my_job.sponsorship_no")
                    : t("my_job.sponsorship_unsure")
              }
              selected={requiresSponsorship === value}
              onPress={() => onSponsorshipChange(value)}
              disabled={busy}
            />
          ))}
        </View>
        <Text style={s.helper}>{t("my_job.sponsorship_helper")}</Text>
      </View>

      <View style={s.fieldGroup}>
        <FieldLabel>{t("my_job.excluded_companies_label")}</FieldLabel>
        <TextInput
          style={s.input}
          value={excludedCompanies}
          onChangeText={onExcludedCompaniesChange}
          placeholder={t("my_job.excluded_companies_placeholder")}
          placeholderTextColor={C.textDisabled}
          editable={!busy}
          autoCapitalize="words"
        />
        <Text style={s.helper}>{t("my_job.excluded_companies_helper")}</Text>
      </View>
    </>
  );
}
