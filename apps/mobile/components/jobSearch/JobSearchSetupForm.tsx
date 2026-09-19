import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Keyboard,
  Platform,
  Pressable,
  ScrollView,
  Text,
  View,
} from "react-native";
import type { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import { useTranslation } from "react-i18next";

import {
  composePlace,
  EMPTY_PLACE,
  parsePlace,
  type PlaceValue,
} from "@/components/jobSearch/LocationFields";
import { DeliveryStep } from "@/components/jobSearch/setup/DeliveryStep";
import { LocationStep } from "@/components/jobSearch/setup/LocationStep";
import { ProfileStep } from "@/components/jobSearch/setup/ProfileStep";
import { RolesSkillsStep } from "@/components/jobSearch/setup/RolesSkillsStep";
import { SetupPickers } from "@/components/jobSearch/setup/SetupPickers";
import {
  formatRunDate,
  nextMorning,
  toggleSelection,
  usableRunDate,
  useSetupStyles,
} from "@/components/jobSearch/setup/setupShared";
import { useAuth } from "@/contexts/AuthContext";
import type {
  JobSearchExperience,
  JobSearchFrequency,
  JobSearchInput,
  JobSearchProfile,
  JobSearchWorkMode,
} from "@/lib/api";
import { pickDocument, uploadChatAttachment } from "@/lib/attachments";
import { useTheme } from "@/lib/theme";

type Step = 0 | 1 | 2 | 3;
type ResultCount = 5 | 10 | 15;

type Props = {
  initial: JobSearchProfile | null;
  busy: boolean;
  onClose: () => void;
  onSave: (input: JobSearchInput) => Promise<boolean>;
};

export function JobSearchSetupForm({ initial, busy, onClose, onSave }: Props) {
  const { token, user } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useSetupStyles();
  const isPro = user?.plan === "pro";
  const [step, setStep] = useState<Step>(0);
  const [roles, setRoles] = useState<string[]>([]);
  const [skills, setSkills] = useState<string[]>([]);
  const [place, setPlace] = useState<PlaceValue>(EMPTY_PLACE);
  const [salary, setSalary] = useState("");
  const [workModes, setWorkModes] = useState<JobSearchWorkMode[]>(["remote"]);
  const [level, setLevel] = useState<JobSearchExperience>("entry");
  const [showExperience, setShowExperience] = useState(false);
  const [count, setCount] = useState<ResultCount>(isPro ? 10 : 5);
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
    } catch {
      Alert.alert(
        t("my_job.resume_upload_failed_title"),
        t("my_job.resume_upload_failed_body"),
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
    const parsedSalary = salary.trim()
      ? Number(salary.replace(/[$,\s]/g, ""))
      : null;
    if (
      parsedSalary != null &&
      (!Number.isFinite(parsedSalary) || parsedSalary < 0)
    ) {
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

  const openSheet = (setter: (visible: boolean) => void) => {
    Keyboard.dismiss();
    setter(true);
  };
  const experienceLabel = (value: JobSearchExperience) =>
    t(`my_job.level_${value}`);
  const frequencyOptionLabel = (value: JobSearchFrequency) =>
    t(`my_job.freq_${value}`);
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
            <Text style={s.title}>{t(`my_job.step${step}_title`)}</Text>
            <Text style={s.subtitle}>{t(`my_job.step${step}_body`)}</Text>
          </View>

          {step === 0 ? (
            <LocationStep
              place={place}
              workModes={workModes}
              busy={busy}
              onPlaceChange={setPlace}
              onWorkModePress={(mode) =>
                setWorkModes((current) => toggleSelection(mode, current))
              }
            />
          ) : null}
          {step === 1 ? (
            <RolesSkillsStep
              roles={roles}
              skills={skills}
              roleError={roleError}
              busy={busy}
              onRolesChange={(next) => {
                setRoles(next);
                if (roleError) setRoleError(false);
              }}
              onSkillsChange={setSkills}
            />
          ) : null}
          {step === 2 ? (
            <ProfileStep
              resumeName={resumeName}
              uploadingResume={uploadingResume}
              levelLabel={experienceLabel(level)}
              salary={salary}
              salaryError={salaryError}
              busy={busy}
              onChooseResume={() => void chooseResume()}
              onRemoveResume={() => {
                setResumeId(null);
                setResumeName(null);
              }}
              onOpenExperience={() => openSheet(setShowExperience)}
              onSalaryChange={(value) => {
                setSalary(value);
                if (salaryError) setSalaryError(false);
              }}
            />
          ) : null}
          {step === 3 ? (
            <DeliveryStep
              count={count}
              frequencyLabel={frequencyOptionLabel(frequency)}
              timeLabel={formatRunDate(nextRunAt)}
              isPro={isPro}
              busy={busy}
              onOpenCount={() => openSheet(setShowCount)}
              onOpenFrequency={() => openSheet(setShowFrequency)}
              onOpenDatePicker={() => openSheet(setShowPicker)}
            />
          ) : null}
        </View>
      </ScrollView>

      <View style={s.footer}>
        <Pressable
          style={({ pressed }) => [
            s.primaryButton,
            pressed && s.pressed,
            busy && s.disabled,
          ]}
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

      <SetupPickers
        isPro={isPro}
        busy={busy}
        showExperience={showExperience}
        showCount={showCount}
        showFrequency={showFrequency}
        showPicker={showPicker}
        level={level}
        count={count}
        frequency={frequency}
        nextRunAt={nextRunAt}
        experienceLabel={experienceLabel}
        frequencyLabel={frequencyOptionLabel}
        onCloseExperience={() => setShowExperience(false)}
        onCloseCount={() => setShowCount(false)}
        onCloseFrequency={() => setShowFrequency(false)}
        onClosePicker={() => setShowPicker(false)}
        onSelectExperience={setLevel}
        onSelectCount={setCount}
        onSelectFrequency={setFrequency}
        onPickerChange={onPickerChange}
      />
    </View>
  );
}
