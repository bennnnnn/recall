import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { SearchableMultiSelect } from "@/components/jobSearch/SearchableMultiSelect";
import { JOB_TITLES } from "@/lib/jobSearch/jobTitles";
import { SKILLS } from "@/lib/jobSearch/skills";

import {
  FieldLabel,
  MAX_ROLES,
  MAX_SKILLS,
  useSetupStyles,
} from "./setupShared";

type Props = {
  roles: string[];
  skills: string[];
  roleError: boolean;
  busy: boolean;
  onRolesChange: (roles: string[]) => void;
  onSkillsChange: (skills: string[]) => void;
};

export function RolesSkillsStep({
  roles,
  skills,
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
