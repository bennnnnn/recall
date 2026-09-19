import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Keyboard,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import type { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { Icon } from "@/components/Icon";
import { SettingsPickerSheet } from "@/components/settings/SettingsPickerSheet";
import { ReminderDateTimePicker } from "@/components/todos/ReminderDateTimePicker";
import { useAuth } from "@/contexts/AuthContext";
import {
  composePlace,
  EMPTY_PLACE,
  LocationFields,
  parsePlace,
  type PlaceValue,
} from "@/components/jobSearch/LocationFields";
import { SearchableMultiSelect } from "@/components/jobSearch/SearchableMultiSelect";
import {
  type JobSearchExperience,
  type JobSearchFrequency,
  type JobSearchInput,
  type JobSearchProfile,
  type JobSearchWorkMode,
} from "@/lib/api";
import { pickDocument, uploadChatAttachment } from "@/lib/attachments";
import { JOB_TITLES } from "@/lib/jobSearch/jobTitles";
import { SKILLS } from "@/lib/jobSearch/skills";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Step = 0 | 1 | 2 | 3;

const WORK_MODE_VALUES: JobSearchWorkMode[] = ["remote", "hybrid", "onsite"];
const EXPERIENCE_VALUES: JobSearchExperience[] = ["internship", "entry", "mid", "senior"];
const FREQUENCY_VALUES: JobSearchFrequency[] = ["daily", "weekdays", "weekly", "monthly"];

/** Backend caps (JobSearchUpsert): target_roles ≤ 6, skills ≤ 30. */
const MAX_ROLES = 6;
const MAX_SKILLS = 30;

function nextMorning(): Date {
  const value = new Date();
  value.setDate(value.getDate() + 1);
  value.setHours(8, 0, 0, 0);
  return value;
}

function usableRunDate(value: string | undefined): Date {
  if (!value) return nextMorning();
  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime()) || parsed.getTime() <= Date.now()) return nextMorning();
  return parsed;
}

function SelectChip<T extends string>({
  value,
  label,
  selected,
  onPress,
  disabled,
}: {
  value: T;
  label: string;
  selected: boolean;
  onPress: (value: T) => void;
  disabled?: boolean;
}) {
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  return (
    <Pressable
      style={({ pressed }) => [
        s.chip,
        selected && s.chipSelected,
        pressed && !disabled && s.pressed,
        disabled && s.disabled,
      ]}
      onPress={() => onPress(value)}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityState={{ selected, disabled: !!disabled }}
    >
      <Text style={[s.chipText, selected && s.chipTextSelected]}>{label}</Text>
    </Pressable>
  );
}

function FieldLabel({ children, optional }: { children: string; optional?: boolean }) {
  const C = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(C), [C]);
  return (
    <View style={s.labelRow}>
      <Text style={s.label}>{children}</Text>
      {optional ? <Text style={s.optional}>{t("my_job.optional")}</Text> : null}
    </View>
  );
}

export function JobSearchSetupForm({
  initial,
  busy,
  onClose,
  onSave,
}: {
  initial: JobSearchProfile | null;
  busy: boolean;
  onClose: () => void;
  onSave: (input: JobSearchInput) => Promise<boolean>;
}) {
  const { token, user } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const isPro = user?.plan === "pro";
  const [step, setStep] = useState<Step>(0);
  const [roles, setRoles] = useState<string[]>([]);
  const [skills, setSkills] = useState<string[]>([]);
  const [place, setPlace] = useState<PlaceValue>(EMPTY_PLACE);
  const [salary, setSalary] = useState("");
  const [workModes, setWorkModes] = useState<JobSearchWorkMode[]>(["remote"]);
  const [level, setLevel] = useState<JobSearchExperience>("entry");
  const [showExperience, setShowExperience] = useState(false);
  const [count, setCount] = useState<5 | 10 | 15>(isPro ? 10 : 5);
  const [frequency, setFrequency] = useState<JobSearchFrequency>(
    isPro ? "weekdays" : "weekly",
  );
  const [showCount, setShowCount] = useState(false);
  const [showFrequency, setShowFrequency] = useState(false);
  const [nextRunAt, setNextRunAt] = useState(nextMorning);
  const [showPicker, setShowPicker] = useState(false);
  const [resumeId, setResumeId] = useState<string | null>(null);
  const [resumeName, setResumeName] = useState<string | null>(null);
  const [uploadingResume, setUploadingResume] = useState(false);
  const [roleError, setRoleError] = useState(false);
  const [salaryError, setSalaryError] = useState(false);

  // Full-screen route: mount = open, so (re)seed the draft when the loaded
  // profile / user arrives.
  useEffect(() => {
    setStep(0);
    setRoleError(false);
    setSalaryError(false);
    setRoles(initial?.target_roles ?? (user?.job ? [user.job] : []));
    setSkills(initial?.skills ?? []);
    setPlace(parsePlace(initial?.location ?? user?.location ?? user?.country ?? ""));
    setSalary(initial?.salary_min ? String(initial.salary_min) : "");
    setWorkModes(initial?.work_modes ?? ["remote"]);
    setLevel(initial?.experience_levels?.[0] ?? "entry");
    setShowExperience(false);
    setCount(isPro ? (initial?.result_count ?? 10) : 5);
    setFrequency(isPro ? (initial?.frequency ?? "weekdays") : "weekly");
    setShowCount(false);
    setShowFrequency(false);
    setNextRunAt(usableRunDate(initial?.next_run_at));
    setResumeId(initial?.resume_attachment_id ?? null);
    setResumeName(initial?.resume_filename ?? null);
    setShowPicker(false);
  }, [initial, user, isPro]);

  const toggle = <T extends string,>(
    value: T,
    values: T[],
    setValues: (next: T[]) => void,
  ) => {
    if (values.includes(value)) {
      if (values.length > 1) setValues(values.filter((item) => item !== value));
    } else {
      setValues([...values, value]);
    }
  };

  const chooseResume = async () => {
    if (!token || uploadingResume) return;
    try {
      const picked = await pickDocument();
      if (!picked) return;
      const allowed =
        picked.contentType === "application/pdf" ||
        picked.contentType === "text/plain" ||
        picked.contentType === "text/markdown" ||
        picked.contentType ===
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
      if (!allowed) {
        Alert.alert(t("my_job.resume_pick_title"), t("my_job.resume_pick_body"));
        return;
      }
      setUploadingResume(true);
      const id = await uploadChatAttachment(token, picked);
      setResumeId(id);
      setResumeName(picked.fileName);
    } catch (error) {
      Alert.alert(
        t("my_job.resume_upload_failed_title"),
        error instanceof Error ? error.message : t("my_job.resume_upload_failed_body"),
      );
    } finally {
      setUploadingResume(false);
    }
  };

  const save = async () => {
    if (roles.length === 0) {
      setRoleError(true);
      setStep(1);
      return;
    }
    const parsedSalary = salary.trim() ? Number(salary.replace(/[$,\s]/g, "")) : null;
    if (parsedSalary != null && (!Number.isFinite(parsedSalary) || parsedSalary < 0)) {
      setSalaryError(true);
      setStep(2);
      return;
    }
    const ok = await onSave({
      target_roles: roles,
      skills,
      location: composePlace(place) || null,
      work_modes: workModes,
      experience_levels: [level],
      salary_min: parsedSalary == null ? null : Math.round(parsedSalary),
      requires_sponsorship: null,
      // The setup form no longer edits exclusions — keep whatever the profile
      // already has so an edit never silently wipes it.
      excluded_companies: initial?.excluded_companies ?? [],
      background: null,
      resume_attachment_id: resumeId,
      result_count: isPro ? count : 5,
      frequency: isPro ? frequency : "weekly",
      next_run_at: nextRunAt.toISOString(),
    });
    if (ok) onClose();
  };

  const onPickerChange = (event: DateTimePickerEvent, date?: Date) => {
    if (Platform.OS === "android") setShowPicker(false);
    if (event.type === "dismissed" || !date) return;
    setNextRunAt(date);
  };

  const moveBack = () => {
    if (busy) return;
    Keyboard.dismiss();
    setShowPicker(false);
    if (step === 0) onClose();
    else setStep((step - 1) as Step);
  };

  const moveForward = async () => {
    Keyboard.dismiss();
    setShowPicker(false);
    if (step === 1 && roles.length === 0) {
      setRoleError(true);
      return;
    }
    if (step < 3) {
      setStep((step + 1) as Step);
      return;
    }
    await save();
  };

  const timeLabel = nextRunAt.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
  const workModeLabel = (value: JobSearchWorkMode) => t(`my_job.work_${value}`);
  const experienceLabel = (value: JobSearchExperience) => t(`my_job.level_${value}`);
  const frequencyOptionLabel = (value: JobSearchFrequency) => t(`my_job.freq_${value}`);
  const frequencyLabel = frequencyOptionLabel(frequency);
  const currentCopy = {
    eyebrow: t(`my_job.step${step}_eyebrow`),
    title: t(`my_job.step${step}_title`),
    body: t(`my_job.step${step}_body`),
  };
  const finalLabel = initial ? t("common.save") : t("my_job.start_search");

  return (
    <View style={s.screen}>
      <View style={s.header}>
        <Pressable
          onPress={moveBack}
          disabled={busy}
          accessibilityRole="button"
          accessibilityLabel={step === 0 ? t("common.cancel") : t("common.back")}
          style={s.headerSide}
        >
          <Text style={s.headerCancel} numberOfLines={1}>
            {step === 0 ? t("common.cancel") : t("common.back")}
          </Text>
        </Pressable>
        <Text style={s.headerTitle} numberOfLines={1}>
          {initial ? t("my_job.edit_title") : t("my_job.setup_title")}
        </Text>
        <View style={s.headerSide} />
      </View>

      <ScrollView
        style={s.flex}
        contentContainerStyle={s.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <View style={s.body}>
        <View style={s.intro}>
          <Text style={s.eyebrow}>{currentCopy.eyebrow}</Text>
          <Text style={s.title}>{currentCopy.title}</Text>
          <Text style={s.subtitle}>{currentCopy.body}</Text>
        </View>

        {step === 0 ? (
          <>
            <View style={s.fieldGroup}>
              <FieldLabel optional>{t("my_job.location_label")}</FieldLabel>
              <LocationFields value={place} onChange={setPlace} disabled={busy} />
            </View>

            <View style={s.fieldGroup}>
              <FieldLabel>{t("my_job.work_mode_label")}</FieldLabel>
              <View style={s.chipRow}>
                {WORK_MODE_VALUES.map((value) => (
                  <SelectChip
                    key={value}
                    value={value}
                    label={workModeLabel(value)}
                    selected={workModes.includes(value)}
                    onPress={(next) => toggle(next, workModes, setWorkModes)}
                    disabled={busy}
                  />
                ))}
              </View>
            </View>
          </>
        ) : null}

        {step === 1 ? (
          <>
            <View style={s.fieldGroup}>
              <FieldLabel>{t("my_job.roles_label")}</FieldLabel>
              <SearchableMultiSelect
                values={roles}
                onChange={(next) => {
                  setRoles(next);
                  if (roleError) setRoleError(false);
                }}
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
              ) : (
                <Text style={s.helper}>{t("my_job.roles_helper")}</Text>
              )}
            </View>

            <View style={s.fieldGroup}>
              <FieldLabel optional>{t("my_job.skills_label")}</FieldLabel>
              <SearchableMultiSelect
                values={skills}
                onChange={setSkills}
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
        ) : null}

        {step === 2 ? (
          <>
            <View style={s.fieldGroup}>
              <FieldLabel optional>{t("my_job.resume_label")}</FieldLabel>
              <Pressable
                style={({ pressed }) => [s.resumeCard, pressed && s.pressed]}
                onPress={() => void chooseResume()}
                disabled={busy || uploadingResume}
                accessibilityRole="button"
                accessibilityLabel={
                  resumeName ? t("my_job.resume_replace_a11y") : t("my_job.resume_upload_a11y")
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
                    {resumeName ? t("my_job.resume_tap_replace") : t("my_job.resume_meta")}
                  </Text>
                </View>
                <Icon name="chevron-forward" size={19} color={C.textTertiary} />
              </Pressable>
              {resumeName ? (
                <Pressable
                  style={s.removeResume}
                  onPress={() => {
                    setResumeId(null);
                    setResumeName(null);
                  }}
                  disabled={busy}
                >
                  <Text style={s.removeResumeText}>{t("my_job.resume_remove")}</Text>
                </Pressable>
              ) : null}
            </View>

            <View style={s.fieldGroup}>
              <FieldLabel>{t("my_job.experience_label")}</FieldLabel>
              <Pressable
                style={({ pressed }) => [s.selectRow, pressed && s.pressed, busy && s.disabled]}
                onPress={() => {
                  Keyboard.dismiss();
                  setShowExperience(true);
                }}
                disabled={busy}
                accessibilityRole="button"
              >
                <Text style={s.selectValue} numberOfLines={1}>
                  {experienceLabel(level)}
                </Text>
                <Icon name="chevron-down" size={18} color={C.textTertiary} />
              </Pressable>
            </View>

            <View style={s.twoColumnRow}>
              <View style={s.flexField}>
                <FieldLabel optional>{t("my_job.salary_label")}</FieldLabel>
                <TextInput
                  style={[s.input, salaryError && s.inputError]}
                  value={salary}
                  onChangeText={(value) => {
                    setSalary(value);
                    if (salaryError) setSalaryError(false);
                  }}
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
        ) : null}

        {step === 3 ? (
          <>
            <View style={s.fieldGroup}>
              <FieldLabel>{t("my_job.count_label")}</FieldLabel>
              <Pressable
                style={({ pressed }) => [s.selectRow, pressed && s.pressed, busy && s.disabled]}
                onPress={() => {
                  Keyboard.dismiss();
                  setShowCount(true);
                }}
                disabled={busy}
                accessibilityRole="button"
              >
                <Text style={s.selectValue} numberOfLines={1}>
                  {count} {t("my_job.count_jobs")}
                </Text>
                <Icon name="chevron-down" size={18} color={C.textTertiary} />
              </Pressable>
            </View>

            <View style={s.fieldGroup}>
              <FieldLabel>{t("my_job.frequency_label")}</FieldLabel>
              <Pressable
                style={({ pressed }) => [s.selectRow, pressed && s.pressed, busy && s.disabled]}
                onPress={() => {
                  Keyboard.dismiss();
                  setShowFrequency(true);
                }}
                disabled={busy}
                accessibilityRole="button"
              >
                <Text style={s.selectValue} numberOfLines={1}>
                  {frequencyLabel}
                </Text>
                <Icon name="chevron-down" size={18} color={C.textTertiary} />
              </Pressable>
              {!isPro ? (
                <Text style={s.helper}>{t("my_job.frequency_free_note")}</Text>
              ) : null}
            </View>

            <View style={s.fieldGroup}>
              <FieldLabel>{t("my_job.first_delivery_label")}</FieldLabel>
              <Pressable
                style={({ pressed }) => [s.dateCard, pressed && s.pressed]}
                onPress={() => {
                  Keyboard.dismiss();
                  setShowPicker(true);
                }}
                disabled={busy}
                accessibilityRole="button"
              >
                <View style={s.dateIcon}>
                  <Icon name="calendar-outline" size={22} color={C.primary} />
                </View>
                <View style={s.dateCopy}>
                  <Text style={s.dateTitle}>{timeLabel}</Text>
                  <Text style={s.dateMeta}>{t("my_job.first_delivery_meta")}</Text>
                </View>
                <Icon name="chevron-down" size={19} color={C.textTertiary} />
              </Pressable>
            </View>

          </>
        ) : null}
        </View>
      </ScrollView>

      <View style={s.footer}>
        <Pressable
          style={({ pressed }) => [s.primaryButton, pressed && s.pressed, busy && s.disabled]}
          onPress={() => void moveForward()}
          disabled={busy}
          accessibilityRole="button"
        >
          {busy ? (
            <ActivityIndicator color={C.onPrimary} />
          ) : (
            <Text style={s.primaryButtonText}>
              {step === 3 ? finalLabel : t("common.next")}
            </Text>
          )}
        </Pressable>
      </View>

      <SettingsPickerSheet
        visible={showExperience}
        options={EXPERIENCE_VALUES.map((value) => ({
          key: value,
          label: experienceLabel(value),
        }))}
        selectedKey={level}
        onClose={() => setShowExperience(false)}
        onSelect={(key) => setLevel(key as JobSearchExperience)}
      />

      <SettingsPickerSheet
        visible={showCount}
        options={([5, 10, 15] as const).map((option) => ({
          key: String(option),
          label: `${option} ${t("my_job.count_jobs")}`,
          disabled: !isPro && option !== 5,
          note: !isPro && option !== 5 ? t("my_job.count_pro") : undefined,
        }))}
        selectedKey={String(count)}
        onClose={() => setShowCount(false)}
        onSelect={(key) => setCount(Number(key) as 5 | 10 | 15)}
      />

      <SettingsPickerSheet
        visible={showFrequency}
        options={FREQUENCY_VALUES.map((value) => ({
          key: value,
          label: frequencyOptionLabel(value),
          disabled: !isPro && value !== "weekly",
          note: !isPro && value !== "weekly" ? t("my_job.count_pro") : undefined,
        }))}
        selectedKey={frequency}
        onClose={() => setShowFrequency(false)}
        onSelect={(key) => setFrequency(key as JobSearchFrequency)}
      />

      {/* Android fires native date→time dialogs from the rendered picker itself;
          iOS gets the spinner inside a floating sheet with a Done button. */}
      {Platform.OS === "android" && showPicker ? (
        <ReminderDateTimePicker value={nextRunAt} onChange={onPickerChange} disabled={busy} />
      ) : null}
      <AppSheet
        visible={Platform.OS === "ios" && showPicker}
        onClose={() => setShowPicker(false)}
        withHandle
      >
        <Text style={s.pickerTitle}>{t("my_job.first_delivery_label")}</Text>
        <ReminderDateTimePicker value={nextRunAt} onChange={onPickerChange} disabled={busy} />
        <Pressable
          style={({ pressed }) => [s.pickerDone, pressed && s.pressed]}
          onPress={() => setShowPicker(false)}
          accessibilityRole="button"
        >
          <Text style={s.pickerDoneText}>{t("common.done")}</Text>
        </Pressable>
      </AppSheet>
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    screen: {
      flex: 1,
      backgroundColor: C.bg,
    },
    flex: { flex: 1 },
    scrollContent: { flexGrow: 1 },
    footer: {
      paddingHorizontal: Space.lg,
      paddingTop: Space.xs,
      paddingBottom: Space.md,
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: Space.md,
      paddingTop: Space.sm,
      gap: Space.sm,
    },
    headerSide: { minWidth: 64, minHeight: 44, justifyContent: "center" },
    headerCancel: { ...Type.body, color: C.textSecondary },
    headerTitle: {
      ...Type.navTitle,
      color: C.text,
      flex: 1,
      textAlign: "center",
    },
    body: {
      paddingHorizontal: Space.lg,
      paddingTop: Space.lg,
      paddingBottom: Space.xl,
      gap: Space.lg,
    },
    intro: { gap: Space.xs },
    eyebrow: { ...Type.overline, color: C.primary },
    title: {
      ...Type.display,
      fontSize: 26,
      lineHeight: 32,
      color: C.text,
    },
    subtitle: { ...Type.body, color: C.textSecondary },
    fieldGroup: { gap: Space.xs },
    labelRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: Space.sm,
    },
    label: { ...Type.label, color: C.text },
    optional: { ...Type.caption, color: C.textTertiary },
    input: {
      ...Type.body,
      minHeight: 54,
      borderRadius: Radius.xl,
      backgroundColor: C.surface,
      color: C.text,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
    },
    inputError: { borderColor: C.danger },
    selectRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      minHeight: 54,
      borderRadius: Radius.xl,
      backgroundColor: C.surface,
      paddingHorizontal: Space.md,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
    },
    selectValue: { ...Type.body, color: C.text, flex: 1 },
    errorText: { ...Type.caption, color: C.danger },
    helper: { ...Type.caption, color: C.textTertiary },
    chipRow: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: Space.xs,
    },
    chip: {
      minHeight: 42,
      paddingHorizontal: Space.md,
      borderRadius: Radius.full,
      backgroundColor: C.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      alignItems: "center",
      justifyContent: "center",
    },
    chipSelected: {
      backgroundColor: C.primaryLight,
      borderColor: C.primary,
    },
    chipText: { ...Type.secondary, fontWeight: "600", color: C.textSecondary },
    chipTextSelected: { color: C.primary },
    resumeCard: {
      minHeight: 72,
      borderRadius: Radius.xl,
      backgroundColor: C.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
    },
    resumeIcon: {
      width: 44,
      height: 44,
      borderRadius: Radius.md,
      backgroundColor: C.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    resumeCopy: { flex: 1, gap: 2 },
    resumeTitle: { ...Type.label, color: C.text },
    resumeMeta: { ...Type.caption, color: C.textTertiary },
    removeResume: { alignSelf: "flex-start", paddingVertical: Space.xxs },
    removeResumeText: { ...Type.secondary, fontWeight: "600", color: C.danger },
    twoColumnRow: { flexDirection: "row", gap: Space.sm },
    flexField: { flex: 1, gap: Space.xs },
    dateCard: {
      minHeight: 72,
      borderRadius: Radius.xl,
      backgroundColor: C.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
    },
    dateIcon: {
      width: 44,
      height: 44,
      borderRadius: Radius.md,
      backgroundColor: C.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    dateCopy: { flex: 1, gap: 2 },
    dateTitle: { ...Type.label, color: C.text },
    dateMeta: { ...Type.caption, color: C.textTertiary },
    pickerTitle: {
      ...Type.navTitle,
      color: C.text,
      fontWeight: "700",
      textAlign: "center",
      marginBottom: Space.xs,
    },
    pickerDone: {
      minHeight: 50,
      borderRadius: Radius.full,
      backgroundColor: C.primary,
      alignItems: "center",
      justifyContent: "center",
      marginTop: Space.sm,
    },
    pickerDoneText: { ...Type.secondary, fontWeight: "700", color: C.onPrimary },
    primaryButton: {
      minHeight: 56,
      borderRadius: Radius.full,
      backgroundColor: C.primary,
      alignItems: "center",
      justifyContent: "center",
      marginTop: Space.xs,
    },
    primaryButtonText: { ...Type.body, fontWeight: "700", color: C.onPrimary },
    pressed: { opacity: 0.72 },
    disabled: { opacity: 0.45 },
  });
}
