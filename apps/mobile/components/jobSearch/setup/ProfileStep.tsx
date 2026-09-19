import { Pressable, Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { useTheme } from "@/lib/theme";

import { FieldLabel, useSetupStyles } from "./setupShared";

type Props = {
  resumeName: string | null;
  uploadingResume: boolean;
  levelLabel: string;
  salary: string;
  salaryError: boolean;
  busy: boolean;
  onChooseResume: () => void;
  onRemoveResume: () => void;
  onOpenExperience: () => void;
  onSalaryChange: (salary: string) => void;
};

export function ProfileStep({
  resumeName,
  uploadingResume,
  levelLabel,
  salary,
  salaryError,
  busy,
  onChooseResume,
  onRemoveResume,
  onOpenExperience,
  onSalaryChange,
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
            <Icon name="document-text-outline" size={23} color={C.primary} />
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
          <Icon name="chevron-forward" size={19} color={C.textTertiary} />
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
        <Pressable
          style={({ pressed }) => [
            s.selectRow,
            pressed && s.pressed,
            busy && s.disabled,
          ]}
          onPress={onOpenExperience}
          disabled={busy}
          accessibilityRole="button"
        >
          <Text style={s.selectValue} numberOfLines={1}>
            {levelLabel}
          </Text>
          <Icon name="chevron-down" size={18} color={C.textTertiary} />
        </Pressable>
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
    </>
  );
}
