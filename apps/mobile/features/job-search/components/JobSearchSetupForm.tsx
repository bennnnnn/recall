import { useEffect, useRef, useState } from "react";
import {
  Keyboard,
  Pressable,
  ScrollView,
  Text,
  View,
} from "react-native";
import { useTranslation } from "react-i18next";

import {
  composePlace,
  EMPTY_PLACE,
  parsePlace,
  type PlaceValue,
} from "@/features/job-search/components/LocationFields";
import { DeliveryStep } from "@/features/job-search/components/setup/DeliveryStep";
import { LocationStep } from "@/features/job-search/components/setup/LocationStep";
import { ProfileStep } from "@/features/job-search/components/setup/ProfileStep";
import { RolesSkillsStep } from "@/features/job-search/components/setup/RolesSkillsStep";
import { SetupPickers } from "@/features/job-search/components/setup/SetupPickers";
import {
  formatRunDate,
  nextMorning,
  toggleSelection,
  usableRunDate,
  useSetupStyles,
} from "@/features/job-search/components/setup/setupShared";
import { useAuth } from "@/contexts/AuthContext";
import {
  type JobSearchExperience,
  type JobSearchFrequency,
  type JobSearchInput,
  type JobSearchProfile,
  type JobSearchWorkMode,
} from "@/lib/api";
import { pickDocument, uploadChatAttachment } from "@/features/attachments/model/attachments";
import { alertDialog } from "@/ui/overlay/dialogs";
import { LocationCollection } from "./LocationCollection";
import { TextField } from "@/ui/controls/TextField";
import { FieldLabel, SelectChip } from "./setup/setupShared";
import { Button } from "@/ui/controls/Button";

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
  const s = useSetupStyles();
  const isPro = user?.plan === "pro";
  const [step, setStep] = useState<Step>(0);
  const [roles, setRoles] = useState<string[]>([]);
  const [skills, setSkills] = useState<string[]>([]);
  const [place, setPlace] = useState<PlaceValue>(EMPTY_PLACE);
  const [salary, setSalary] = useState("");
  const [currency, setCurrency] = useState("");
  const [salaryPeriod, setSalaryPeriod] = useState<"year" | "month" | "week" | "hour">("year");
  const [years, setYears] = useState("");
  const [additionalPlaces, setAdditionalPlaces] = useState<PlaceValue[]>([]);
  const [excludedPlaces, setExcludedPlaces] = useState<PlaceValue[]>([]);
  const [workModes, setWorkModes] = useState<JobSearchWorkMode[]>(["remote", "hybrid", "onsite"]);
  const [levels, setLevels] = useState<JobSearchExperience[]>(["internship", "entry", "mid", "senior"]);
  const [requiresSponsorship, setRequiresSponsorship] = useState<boolean | null>(null);
  const [excludedCompanies, setExcludedCompanies] = useState("");
  const [count, setCount] = useState<ResultCount>(10);
  const [frequency, setFrequency] = useState<JobSearchFrequency>(
    "weekdays",
  );
  const [showCount, setShowCount] = useState(false);
  const [showFrequency, setShowFrequency] = useState(false);
  const countRowRef = useRef<View>(null);
  const frequencyRowRef = useRef<View>(null);
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
    const places = (initial?.included_locations ?? []).map(item => ({ country: item.country, region: item.region ?? "", city: item.city ?? "" }));
    setPlace(places[0] ?? parsePlace(initial?.location ?? user?.location ?? user?.country ?? ""));
    setAdditionalPlaces(places.slice(1));
    setExcludedPlaces((initial?.excluded_locations ?? []).map(item => ({ country: item.country, region: item.region ?? "", city: item.city ?? "" })));
    setCurrency(initial?.salary_currency ?? "");
    setSalaryPeriod(initial?.salary_period ?? "year");
    setYears(initial?.years_experience == null ? "" : String(initial.years_experience));
    setSalary(initial?.salary_min ? String(initial.salary_min) : "");
    setWorkModes(initial?.work_modes ?? ["remote", "hybrid", "onsite"]);
    setLevels(initial?.experience_levels?.length ? initial.experience_levels : ["internship", "entry", "mid", "senior"]);
    setRequiresSponsorship(initial?.requires_sponsorship ?? null);
    setExcludedCompanies((initial?.excluded_companies ?? []).join(", "));
    setCount(initial?.result_count ?? 10);
    setFrequency(initial?.frequency ?? "weekdays");
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
        void alertDialog({
          title: t("my_job.resume_pick_title"),
          message: t("my_job.resume_pick_body"),
        });
        return;
      }
      setUploadingResume(true);
      const id = await uploadChatAttachment(token, picked);
      setResumeId(id);
      setResumeName(picked.fileName);
    } catch {
      void alertDialog({
        title: t("my_job.resume_upload_failed_title"),
        message: t("my_job.resume_upload_failed_body"),
      });
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
    if (!place.country || (parsedSalary != null && !/^[A-Z]{3}$/.test(currency)) || (years.trim() && (!Number.isFinite(Number(years)) || Number(years) < 0 || Number(years) > 80))) {
      void alertDialog({ title: t("my_job.preferences_review"), message: !place.country ? t("my_job.country_required") : years.trim() && (!Number.isFinite(Number(years)) || Number(years) < 0 || Number(years) > 80) ? t("my_job.experience_invalid") : t("my_job.currency_required") });
      return;
    }
    const ok = await onSave({
      expected_revision: initial?.revision,
      included_locations: [place, ...additionalPlaces],
      excluded_locations: excludedPlaces,
      country: place.country,
      salary_currency: currency || null,
      salary_period: salaryPeriod,
      years_experience: years.trim() ? Number(years) : null,
      target_roles: roles,
      skills,
      location: composePlace(place) || null,
      work_modes: workModes,
      experience_levels: levels,
      salary_min: parsedSalary == null ? null : Math.round(parsedSalary),
      requires_sponsorship: requiresSponsorship,
      excluded_companies: excludedCompanies
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean),
      background: initial?.background ?? null,
      resume_attachment_id: resumeId,
      result_count: count,
      frequency,
      next_run_at: nextRunAt.toISOString(),
    });
    if (ok) onClose();
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
    if (step === 0 && !place.country) {
      void alertDialog({ title: t("my_job.location_label"), message: t("my_job.country_required") });
      return;
    }
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
  const reviewSummary = [
    roles.join(" · "),
    composePlace(place) || t("my_job.any_location"),
    workModes.map((value) => t(`my_job.work_${value}`)).join(" · "),
    levels.map((value) => experienceLabel(value)).join(" · "),
  ].filter(Boolean);

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

      <View
        style={s.progressWrap}
        accessibilityLabel={t("my_job.setup_progress", {
          current: step + 1,
          total: 4,
        })}
      >
        <View style={s.progressRow}>
          {([0, 1, 2, 3] as const).map((index) => (
            <View
              key={index}
              style={[s.progressSegment, index <= step && s.progressSegmentActive]}
            />
          ))}
        </View>
        <Text style={s.progressText}>
          {t("my_job.setup_progress", { current: step + 1, total: 4 })}
        </Text>
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
            <>
            <LocationStep
              place={place}
              workModes={workModes}
              busy={busy}
              onPlaceChange={setPlace}
              onWorkModePress={(mode) =>
                setWorkModes((current) => toggleSelection(mode, current))
              }
            />
            <LocationCollection included={additionalPlaces} excluded={excludedPlaces} onIncluded={setAdditionalPlaces} onExcluded={setExcludedPlaces} disabled={busy} />
            </>
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
            <>
            <View style={s.fieldGroup}>
              <FieldLabel>{t("my_job.actual_experience")}</FieldLabel>
              <TextField value={years} onChangeText={setYears} keyboardType="decimal-pad" placeholder={t("my_job.optional")} editable={!busy} />
            </View>
            <ProfileStep
              resumeName={resumeName}
              uploadingResume={uploadingResume}
              levels={levels}
              salary={salary}
              requiresSponsorship={requiresSponsorship}
              excludedCompanies={excludedCompanies}
              salaryError={salaryError}
              busy={busy}
              onChooseResume={() => void chooseResume()}
              onRemoveResume={() => {
                setResumeId(null);
                setResumeName(null);
              }}
              onExperiencePress={(level) =>
                setLevels((current) => toggleSelection(level, current))
              }
              onSalaryChange={(value) => {
                setSalary(value);
                if (salaryError) setSalaryError(false);
              }}
              onSponsorshipChange={setRequiresSponsorship}
              onExcludedCompaniesChange={setExcludedCompanies}
            />
            <View style={s.fieldGroup}>
              <FieldLabel>{t("my_job.salary_currency")}</FieldLabel>
              <TextField value={currency} onChangeText={value => setCurrency(value.toUpperCase())} placeholder="USD / EUR / CAD" maxLength={3} autoCapitalize="characters" editable={!busy} />
              <View style={s.chipRow}>{(["year", "month", "week", "hour"] as const).map(period => <SelectChip key={period} value={period} label={t(`my_job.pay_${period}`)} selected={salaryPeriod === period} onPress={() => setSalaryPeriod(period)} disabled={busy} />)}</View>
            </View>
            </>
          ) : null}
          {step === 3 ? (
            <DeliveryStep
              countRowRef={countRowRef}
              frequencyRowRef={frequencyRowRef}
              count={count}
              frequencyLabel={frequencyOptionLabel(frequency)}
              timeLabel={formatRunDate(nextRunAt)}
              isPro={isPro}
              busy={busy}
              summary={reviewSummary}
              onOpenCount={() => openSheet(setShowCount)}
              onOpenFrequency={() => openSheet(setShowFrequency)}
              onOpenDatePicker={() => openSheet(setShowPicker)}
            />
          ) : null}
        </View>
      </ScrollView>

      <View style={s.footer}>
        <Button
          title={step === 3 ? finalLabel : t("common.next")}
          size="lg"
          loading={busy}
          onPress={() => void moveForward()}
          style={s.primaryButton}
        />
      </View>

      <SetupPickers
        countRowRef={countRowRef}
        frequencyRowRef={frequencyRowRef}
        isPro={isPro}
        busy={busy}
        showCount={showCount}
        showFrequency={showFrequency}
        showPicker={showPicker}
        count={count}
        frequency={frequency}
        nextRunAt={nextRunAt}
        frequencyLabel={frequencyOptionLabel}
        onCloseCount={() => setShowCount(false)}
        onCloseFrequency={() => setShowFrequency(false)}
        onClosePicker={() => setShowPicker(false)}
        onSelectCount={setCount}
        onSelectFrequency={setFrequency}
        onPickNextRun={setNextRunAt}
      />
    </View>
  );
}
