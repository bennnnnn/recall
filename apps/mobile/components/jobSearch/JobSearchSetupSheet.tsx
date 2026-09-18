import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Keyboard,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import type { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { Icon } from "@/components/Icon";
import { SheetFormHeader } from "@/components/SheetFormHeader";
import { ReminderDateTimePicker } from "@/components/todos/ReminderDateTimePicker";
import { useAuth } from "@/contexts/AuthContext";
import {
  type JobSearchExperience,
  type JobSearchFrequency,
  type JobSearchInput,
  type JobSearchProfile,
  type JobSearchWorkMode,
} from "@/lib/api";
import { pickDocument, uploadChatAttachment } from "@/lib/attachments";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Step = 0 | 1 | 2;

const STEP_KEYS = [0, 1, 2] as const;

const WORK_MODE_VALUES: JobSearchWorkMode[] = ["remote", "hybrid", "onsite"];
const EXPERIENCE_VALUES: JobSearchExperience[] = ["internship", "entry", "mid", "senior"];
const FREQUENCY_VALUES: JobSearchFrequency[] = ["daily", "weekdays", "weekly", "monthly"];

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

function join(values: string[]): string {
  return values.join(", ");
}

function split(value: string): string[] {
  return Array.from(
    new Map(
      value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean)
        .map((item) => [item.toLowerCase(), item]),
    ).values(),
  );
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

export function JobSearchSetupSheet({
  visible,
  initial,
  busy,
  onClose,
  onSave,
}: {
  visible: boolean;
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
  const [roles, setRoles] = useState("");
  const [skills, setSkills] = useState("");
  const [location, setLocation] = useState("");
  const [excluded, setExcluded] = useState("");
  const [background, setBackground] = useState("");
  const [salary, setSalary] = useState("");
  const [workModes, setWorkModes] = useState<JobSearchWorkMode[]>(["remote"]);
  const [levels, setLevels] = useState<JobSearchExperience[]>(["entry"]);
  const [sponsorship, setSponsorship] = useState<boolean | null>(null);
  const [count, setCount] = useState<5 | 10 | 15>(isPro ? 10 : 5);
  const [frequency, setFrequency] = useState<JobSearchFrequency>(
    isPro ? "weekdays" : "weekly",
  );
  const [nextRunAt, setNextRunAt] = useState(nextMorning);
  const [showPicker, setShowPicker] = useState(false);
  const [resumeId, setResumeId] = useState<string | null>(null);
  const [resumeName, setResumeName] = useState<string | null>(null);
  const [uploadingResume, setUploadingResume] = useState(false);
  const [roleError, setRoleError] = useState(false);
  const [salaryError, setSalaryError] = useState(false);

  useEffect(() => {
    if (!visible) return;
    setStep(0);
    setRoleError(false);
    setSalaryError(false);
    setRoles(join(initial?.target_roles ?? (user?.job ? [user.job] : [])));
    setSkills(join(initial?.skills ?? []));
    setLocation(initial?.location ?? user?.location ?? user?.country ?? "");
    setExcluded(join(initial?.excluded_companies ?? []));
    setBackground(initial?.background ?? "");
    setSalary(initial?.salary_min ? String(initial.salary_min) : "");
    setWorkModes(initial?.work_modes ?? ["remote"]);
    setLevels(initial?.experience_levels ?? ["entry"]);
    setSponsorship(initial?.requires_sponsorship ?? null);
    setCount(isPro ? (initial?.result_count ?? 10) : 5);
    setFrequency(isPro ? (initial?.frequency ?? "weekdays") : "weekly");
    setNextRunAt(usableRunDate(initial?.next_run_at));
    setResumeId(initial?.resume_attachment_id ?? null);
    setResumeName(initial?.resume_filename ?? null);
    setShowPicker(false);
  }, [visible, initial, user, isPro]);

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
    const targetRoles = split(roles);
    if (targetRoles.length === 0) {
      setRoleError(true);
      setStep(0);
      return;
    }
    const parsedSalary = salary.trim() ? Number(salary.replace(/[$,\s]/g, "")) : null;
    if (parsedSalary != null && (!Number.isFinite(parsedSalary) || parsedSalary < 0)) {
      setSalaryError(true);
      setStep(1);
      return;
    }
    const ok = await onSave({
      target_roles: targetRoles,
      skills: split(skills),
      location: location.trim() || null,
      work_modes: workModes,
      experience_levels: levels,
      salary_min: parsedSalary == null ? null : Math.round(parsedSalary),
      requires_sponsorship: sponsorship,
      excluded_companies: split(excluded),
      background: background.trim() || null,
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
    if (step === 0 && split(roles).length === 0) {
      setRoleError(true);
      return;
    }
    if (step < 2) {
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
  const roleSummary = split(roles).slice(0, 2).join(" · ") || t("my_job.summary_roles_fallback");
  const currentCopy = {
    eyebrow: t(`my_job.step${step}_eyebrow`),
    title: t(`my_job.step${step}_title`),
    body: t(`my_job.step${step}_body`),
  };
  const finalLabel = initial ? t("common.save") : t("my_job.start_search");

  return (
    <AppSheet
      visible={visible}
      onClose={busy ? () => {} : onClose}
      variant="bottom"
      keyboardAvoiding
      withHandle={false}
      contentContainerStyle={s.sheet}
    >
      <SheetFormHeader
        title={initial ? t("my_job.edit_title") : t("my_job.setup_title")}
        onCancel={moveBack}
        onSave={() => void moveForward()}
        cancelLabel={step === 0 ? t("common.cancel") : t("common.back")}
        saveLabel={step === 2 ? finalLabel : t("common.next")}
        saving={busy}
      />

      <View style={s.progressWrap}>
        <View style={s.progressBars}>
          {STEP_KEYS.map((value) => (
            <View
              key={value}
              style={[s.progressBar, value <= step && s.progressBarActive]}
            />
          ))}
        </View>
        <Text style={s.progressText}>
          {t("my_job.step_progress", { step: step + 1, total: STEP_KEYS.length })}
        </Text>
      </View>

      <View style={s.body}>
        <View style={s.intro}>
          <Text style={s.eyebrow}>{currentCopy.eyebrow}</Text>
          <Text style={s.title}>{currentCopy.title}</Text>
          <Text style={s.subtitle}>{currentCopy.body}</Text>
        </View>

        {step === 0 ? (
          <>
            <View style={s.fieldGroup}>
              <FieldLabel>{t("my_job.roles_label")}</FieldLabel>
              <TextInput
                style={[s.input, roleError && s.inputError]}
                value={roles}
                onChangeText={(value) => {
                  setRoles(value);
                  if (roleError) setRoleError(false);
                }}
                placeholder={t("my_job.roles_placeholder")}
                placeholderTextColor={C.textDisabled}
                editable={!busy}
                autoCapitalize="words"
                returnKeyType="next"
                autoFocus={!initial}
              />
              {roleError ? (
                <Text style={s.errorText}>{t("my_job.role_required_body")}</Text>
              ) : (
                <Text style={s.helper}>{t("my_job.roles_helper")}</Text>
              )}
            </View>

            <View style={s.fieldGroup}>
              <FieldLabel optional>{t("my_job.skills_label")}</FieldLabel>
              <TextInput
                style={s.input}
                value={skills}
                onChangeText={setSkills}
                placeholder={t("my_job.skills_placeholder")}
                placeholderTextColor={C.textDisabled}
                editable={!busy}
                autoCapitalize="none"
              />
            </View>

            <View style={s.fieldGroup}>
              <FieldLabel optional>{t("my_job.location_label")}</FieldLabel>
              <TextInput
                style={s.input}
                value={location}
                onChangeText={setLocation}
                placeholder={t("my_job.location_placeholder")}
                placeholderTextColor={C.textDisabled}
                editable={!busy}
              />
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
              <FieldLabel>{t("my_job.experience_label")}</FieldLabel>
              <View style={s.chipRow}>
                {EXPERIENCE_VALUES.map((value) => (
                  <SelectChip
                    key={value}
                    value={value}
                    label={experienceLabel(value)}
                    selected={levels.includes(value)}
                    onPress={(next) => toggle(next, levels, setLevels)}
                    disabled={busy}
                  />
                ))}
              </View>
            </View>

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
              <FieldLabel optional>{t("my_job.background_label")}</FieldLabel>
              <TextInput
                style={[s.input, s.multiline]}
                value={background}
                onChangeText={setBackground}
                placeholder={t("my_job.background_placeholder")}
                placeholderTextColor={C.textDisabled}
                editable={!busy}
                multiline
                textAlignVertical="top"
              />
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

            <View style={s.fieldGroup}>
              <FieldLabel optional>{t("my_job.sponsorship_label")}</FieldLabel>
              <View style={s.chipRow}>
                <SelectChip
                  value="no"
                  label={t("my_job.sponsorship_no")}
                  selected={sponsorship === false}
                  onPress={() => setSponsorship(false)}
                  disabled={busy}
                />
                <SelectChip
                  value="yes"
                  label={t("my_job.sponsorship_yes")}
                  selected={sponsorship === true}
                  onPress={() => setSponsorship(true)}
                  disabled={busy}
                />
                <SelectChip
                  value="skip"
                  label={t("my_job.sponsorship_skip")}
                  selected={sponsorship == null}
                  onPress={() => setSponsorship(null)}
                  disabled={busy}
                />
              </View>
            </View>

            <View style={s.fieldGroup}>
              <FieldLabel optional>{t("my_job.excluded_label")}</FieldLabel>
              <TextInput
                style={s.input}
                value={excluded}
                onChangeText={setExcluded}
                placeholder={t("my_job.excluded_placeholder")}
                placeholderTextColor={C.textDisabled}
                editable={!busy}
              />
            </View>
          </>
        ) : null}

        {step === 2 ? (
          <>
            <View style={s.fieldGroup}>
              <FieldLabel>{t("my_job.count_label")}</FieldLabel>
              <View style={s.countRow}>
                {([5, 10, 15] as const).map((option) => {
                  const locked = !isPro && option !== 5;
                  const selected = count === option;
                  return (
                    <Pressable
                      key={option}
                      style={({ pressed }) => [
                        s.countCard,
                        selected && s.countCardSelected,
                        pressed && !locked && s.pressed,
                        locked && s.disabled,
                      ]}
                      onPress={() => setCount(option)}
                      disabled={busy || locked}
                      accessibilityRole="button"
                      accessibilityState={{ selected, disabled: locked }}
                    >
                      <Text style={[s.countNumber, selected && s.countNumberSelected]}>
                        {option}
                      </Text>
                      <Text style={[s.countLabel, selected && s.countLabelSelected]}>
                        {locked ? t("my_job.count_pro") : t("my_job.count_jobs")}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>

            <View style={s.fieldGroup}>
              <FieldLabel>{t("my_job.frequency_label")}</FieldLabel>
              <View style={s.chipRow}>
                {FREQUENCY_VALUES.map((value) => {
                  const locked = !isPro && value !== "weekly";
                  return (
                    <SelectChip
                      key={value}
                      value={value}
                      label={frequencyOptionLabel(value)}
                      selected={frequency === value}
                      onPress={setFrequency}
                      disabled={busy || locked}
                    />
                  );
                })}
              </View>
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
                  setShowPicker((current) => !current);
                }}
                disabled={busy}
                accessibilityRole="button"
                accessibilityState={{ expanded: showPicker }}
              >
                <View style={s.dateIcon}>
                  <Icon name="calendar-outline" size={22} color={C.primary} />
                </View>
                <View style={s.dateCopy}>
                  <Text style={s.dateTitle}>{timeLabel}</Text>
                  <Text style={s.dateMeta}>{t("my_job.first_delivery_meta")}</Text>
                </View>
                <Icon
                  name={showPicker ? "chevron-up" : "chevron-down"}
                  size={19}
                  color={C.textTertiary}
                />
              </Pressable>
              {showPicker ? (
                <View style={s.pickerWrap}>
                  <ReminderDateTimePicker
                    value={nextRunAt}
                    onChange={onPickerChange}
                    disabled={busy}
                  />
                </View>
              ) : null}
            </View>

            <View style={s.summaryCard}>
              <View style={s.summaryTop}>
                <View style={s.summaryIcon}>
                  <Icon name="briefcase-outline" size={22} color={C.primary} />
                </View>
                <View style={s.summaryCopy}>
                  <Text style={s.summaryEyebrow}>{t("my_job.summary_eyebrow")}</Text>
                  <Text style={s.summaryTitle} numberOfLines={2}>
                    {roleSummary}
                  </Text>
                </View>
              </View>
              <View style={s.summaryDivider} />
              <View style={s.summaryRow}>
                <Text style={s.summaryLabel}>{t("my_job.summary_delivery")}</Text>
                <Text style={s.summaryValue}>
                  {t("my_job.summary_delivery_value", {
                    count: isPro ? count : 5,
                    frequency: isPro ? frequencyLabel : t("my_job.freq_weekly"),
                  })}
                </Text>
              </View>
              <View style={s.summaryRow}>
                <Text style={s.summaryLabel}>{t("my_job.summary_work_mode")}</Text>
                <Text style={s.summaryValue}>{workModes.map(workModeLabel).join(" / ")}</Text>
              </View>
              <View style={s.summaryRow}>
                <Text style={s.summaryLabel}>{t("my_job.summary_starts")}</Text>
                <Text style={s.summaryValue}>{timeLabel}</Text>
              </View>
            </View>
          </>
        ) : null}
      </View>
    </AppSheet>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    sheet: {
      backgroundColor: C.bg,
      borderTopLeftRadius: Radius.sheet,
      borderTopRightRadius: Radius.sheet,
    },
    progressWrap: {
      paddingHorizontal: Space.lg,
      paddingTop: Space.md,
      gap: Space.xs,
    },
    progressBars: {
      flexDirection: "row",
      gap: Space.xs,
    },
    progressBar: {
      flex: 1,
      height: 4,
      borderRadius: Radius.full,
      backgroundColor: C.surfaceAlt,
    },
    progressBarActive: { backgroundColor: C.primary },
    progressText: { ...Type.caption, color: C.textTertiary },
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
    multiline: { minHeight: 112 },
    inputError: { borderColor: C.danger },
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
    countRow: { flexDirection: "row", gap: Space.sm },
    countCard: {
      flex: 1,
      minHeight: 82,
      borderRadius: Radius.xl,
      backgroundColor: C.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      alignItems: "center",
      justifyContent: "center",
      gap: 2,
    },
    countCardSelected: {
      backgroundColor: C.primaryLight,
      borderColor: C.primary,
    },
    countNumber: { ...Type.title, fontWeight: "700", color: C.text },
    countNumberSelected: { color: C.primary },
    countLabel: { ...Type.caption, color: C.textTertiary },
    countLabelSelected: { color: C.primary },
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
    pickerWrap: {
      borderRadius: Radius.xl,
      overflow: "hidden",
      backgroundColor: C.surface,
      paddingVertical: Platform.OS === "ios" ? Space.xs : 0,
    },
    summaryCard: {
      borderRadius: Radius.xl,
      backgroundColor: C.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      padding: Space.md,
      gap: Space.sm,
    },
    summaryTop: { flexDirection: "row", alignItems: "center", gap: Space.sm },
    summaryIcon: {
      width: 46,
      height: 46,
      borderRadius: Radius.md,
      backgroundColor: C.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    summaryCopy: { flex: 1, gap: 2 },
    summaryEyebrow: { ...Type.overline, color: C.primary },
    summaryTitle: { ...Type.navTitle, color: C.text },
    summaryDivider: { height: StyleSheet.hairlineWidth, backgroundColor: C.border },
    summaryRow: {
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "flex-start",
      gap: Space.md,
    },
    summaryLabel: { ...Type.secondary, color: C.textSecondary },
    summaryValue: {
      ...Type.secondary,
      fontWeight: "600",
      color: C.text,
      textAlign: "right",
      flex: 1,
    },
    pressed: { opacity: 0.72 },
    disabled: { opacity: 0.45 },
  });
}
