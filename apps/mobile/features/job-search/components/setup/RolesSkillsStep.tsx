import { Text, View } from "react-native";
import { TextField } from "@/ui/controls/TextField";
import { useTranslation } from "react-i18next";

import { SearchableMultiSelect } from "@/features/job-search/components/SearchableMultiSelect";
import { JOB_TITLES } from "@/features/job-search/model/jobTitles";
import { SKILLS } from "@/features/job-search/model/skills";

import {
  FieldLabel,
  MAX_ROLES,
  MAX_SKILLS,
  useSetupStyles,
} from "./setupShared";

type Props = {
  roles: string[];
  skills: string[];
  years: string;
  onYearsChange: (years: string) => void;
  roleError: boolean;
  busy: boolean;
  onRolesChange: (roles: string[]) => void;
  onSkillsChange: (skills: string[]) => void;
};

export function RolesSkillsStep({
  roles,
  skills,
  years,
  onYearsChange,
  roleError,
  busy,
  onRolesChange,
  onSkillsChange,
}: Props) {
  const { t } = useTranslation();
  const s = useSetupStyles();

  return (
    <>
      <View style={s.fieldGroup}>
        <FieldLabel>{t("my_job.roles_label")}</FieldLabel>
        <SearchableMultiSelect
          values={roles}
          onChange={onRolesChange}
          options={JOB_TITLES}
          placeholder={t("my_job.roles_select_placeholder")}
          sheetTitle={t("my_job.roles_label")}
          searchPlaceholder={t("my_job.roles_search_placeholder")}
          maxSelections={MAX_ROLES}
          disabled={busy}
          invalid={roleError}
        />
        {roleError ? (
          <Text style={s.errorText}>{t("my_job.role_required_body")}</Text>
        ) : null}
      </View>

      <View style={s.fieldGroup}>
        <FieldLabel>{t("my_job.actual_experience")}</FieldLabel>
        <TextField
          value={years}
          onChangeText={onYearsChange}
          accessibilityLabel={t("my_job.actual_experience")}
          keyboardType="decimal-pad"
          placeholder={t("my_job.optional")}
          editable={!busy}
        />
      </View>

      <View style={s.fieldGroup}>
        <FieldLabel>{t("my_job.skills_label")}</FieldLabel>
        <SearchableMultiSelect
          values={skills}
          onChange={onSkillsChange}
          options={SKILLS}
          placeholder={t("my_job.skills_select_placeholder")}
          sheetTitle={t("my_job.skills_label")}
          searchPlaceholder={t("my_job.skills_search_placeholder")}
          maxSelections={MAX_SKILLS}
          disabled={busy}
        />
        <Text style={s.helper}>{t("my_job.skills_helper")}</Text>
      </View>
    </>
  );
}
