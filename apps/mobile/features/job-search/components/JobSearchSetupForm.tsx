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
import { alertDialog } from "@/ui/overlay/dialogs";
import { FieldLabel, SelectChip } from "./setup/setupShared";
import { countryCurrency } from "@/features/job-search/model/countryCurrency";
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
  const { user } = useAuth();
  const { t } = useTranslation();
  const s = useSetupStyles();
  const isPro = user?.plan === "pro";
  const [step, setStep] = useState<Step>(0);
  const [roles, setRoles] = useState<string[]>([]);
  const [skills, setSkills] = useState<string[]>([]);
  const [place, setPlace] = useState<PlaceValue>(EMPTY_PLACE);
  const [salary, setSalary] = useState("");
  const [salaryPeriod, setSalaryPeriod] = useState<"year" | "month" | "week" | "hour">("year");
  const [years, setYears] = useState("");
  const [workModes, setWorkModes] = useState<JobSearchWorkMode[]>(["remote", "hybrid", "onsite"]);
  const [levels, setLevels] = useState<JobSearchExperience[]>(["internship", "entry", "mid", "senior"]);
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
  const [roleError, setRoleError] = useState(false);
  const [salaryError, setSalaryError] = useState<string | null>(null);
  const seededRef = useRef(false);

  // The route waits for the profile before mounting. Keep the draft when auth
  // refreshes or an optimistic save replaces the profile object.
  useEffect(() => {
    if (seededRef.current) return;
    seededRef.current = true;
    setStep(0);
    setRoleError(false);
    setSalaryError(null);
    setRoles(initial?.target_roles ?? (user?.job ? [user.job] : []));
    setSkills(initial?.skills ?? []);
    const places = (initial?.included_locations ?? []).map(item => ({ country: item.country, region: item.region ?? "", city: item.city ?? "" }));
    setPlace(places[0] ?? parsePlace(initial?.location ?? user?.location ?? user?.country ?? ""));
    setSalaryPeriod(initial?.salary_period ?? "year");
    setYears(initial?.years_experience == null ? "" : String(initial.years_experience));
    setSalary(initial?.salary_min ? String(initial.salary_min) : "");
    setWorkModes(initial?.work_modes ?? ["remote", "hybrid", "onsite"]);
    setLevels(initial?.experience_levels?.length ? initial.experience_levels : ["internship", "entry", "mid", "senior"]);
    setCount(initial?.result_count ?? 10);
    setFrequency(initial?.frequency ?? "weekdays");
    setShowCount(false);
    setShowFrequency(false);
    setNextRunAt(usableRunDate(initial?.next_run_at));
    setShowPicker(false);
  }, [initial, user, isPro]);

  const salaryCurrency = initial?.salary_currency ?? countryCurrency(place.country);

  const save = async () => {
    if (roles.length === 0) {
      setRoleError(true);
      setStep(1);
      return;
    }
    const parsedSalary = salary.trim() ? Number(salary) : null;
    if (parsedSalary != null && (!/^\d+$/.test(salary) || !Number.isFinite(parsedSalary) || parsedSalary > 1_000_000_000 || !salaryCurrency)) {
      setSalaryError(t(!salaryCurrency ? "my_job.currency_required" : "my_job.salary_invalid_body"));
      setStep(2);
      return;
    }
    if (!place.country || (years.trim() && (!Number.isFinite(Number(years)) || Number(years) < 0 || Number(years) > 80))) {
      void alertDialog({ title: t("my_job.preferences_review"), message: !place.country ? t("my_job.country_required") : t("my_job.experience_invalid") });
      if (place.country) setStep(1);
      return;
    }
    // Hidden preferences remain available through chat and must survive form edits.
    const includedLocations = [place, ...(initial?.included_locations ?? []).slice(1)];
    const countries = new Set(includedLocations.map(location => location.country));
    const ok = await onSave({
      expected_revision: initial?.revision,
      included_locations: includedLocations,
      excluded_locations: initial?.excluded_locations ?? [],
      country: countries.size === 1 ? place.country : null,
      salary_currency: salaryCurrency,
      salary_period: salaryPeriod,
      years_experience: years.trim() ? Number(years) : null,
      target_roles: roles,
      skills,
      location: composePlace(place) || null,
      work_modes: workModes,
      experience_levels: levels,
      salary_min: parsedSalary,
      requires_sponsorship: initial?.requires_sponsorship ?? null,
      excluded_companies: initial?.excluded_companies ?? [],
      background: initial?.background ?? null,
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
              years={years}
              onYearsChange={setYears}
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
            <ProfileStep
              levels={levels}
              salary={salary}
              salaryCurrency={salaryCurrency}
              salaryError={salaryError}
              busy={busy}
              onExperiencePress={(level) =>
                setLevels((current) => toggleSelection(level, current))
              }
              onSalaryChange={(value) => {
                setSalary(value.replace(/\D/g, ""));
                if (salaryError) setSalaryError(null);
              }}
            />
            <View style={s.fieldGroup}>
              <FieldLabel>{t("my_job.salary_period")}</FieldLabel>
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
