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

function nextMorning(): Date {
  const value = new Date();
  value.setDate(value.getDate() + 1);
  value.setHours(8, 0, 0, 0);
  return value;
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

function Chip<T extends string>({
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
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const isPro = user?.plan === "pro";
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
  const [frequency, setFrequency] = useState<JobSearchFrequency>(isPro ? "weekdays" : "weekly");
  const [nextRunAt, setNextRunAt] = useState(nextMorning);
  const [showPicker, setShowPicker] = useState(Platform.OS === "ios");
  const [resumeId, setResumeId] = useState<string | null>(null);
  const [resumeName, setResumeName] = useState<string | null>(null);
  const [uploadingResume, setUploadingResume] = useState(false);

  useEffect(() => {
    if (!visible) return;
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
    setNextRunAt(initial ? new Date(initial.next_run_at) : nextMorning());
    setResumeId(initial?.resume_attachment_id ?? null);
    setResumeName(initial?.resume_filename ?? null);
    setShowPicker(Platform.OS === "ios");
  }, [visible, initial, user, isPro]);

  const toggle = <T extends string>(value: T, values: T[], setValues: (next: T[]) => void) => {
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
        Alert.alert("Choose a resume", "Upload a PDF, DOCX, or text file.");
        return;
      }
      setUploadingResume(true);
      const id = await uploadChatAttachment(token, picked);
      setResumeId(id);
      setResumeName(picked.fileName);
    } catch (error) {
      Alert.alert(
        "Could not upload resume",
        error instanceof Error ? error.message : "Please try another file.",
      );
    } finally {
      setUploadingResume(false);
    }
  };

  const save = async () => {
    const targetRoles = split(roles);
    if (targetRoles.length === 0) {
      Alert.alert("Add a target role", "For example: Backend Engineer or Platform Engineer.");
      return;
    }
    const parsedSalary = salary.trim() ? Number(salary.replace(/[$,\s]/g, "")) : null;
    if (parsedSalary != null && (!Number.isFinite(parsedSalary) || parsedSalary < 0)) {
      Alert.alert("Check the salary", "Enter a yearly minimum such as 100000.");
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

  const timeLabel = nextRunAt.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });

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
        title={initial ? "Edit job search" : "Set up My Job"}
        onCancel={onClose}
        onSave={() => void save()}
        cancelLabel="Cancel"
        saveLabel={initial ? "Save" : "Start search"}
        saving={busy}
        saveDisabled={!roles.trim() || uploadingResume}
      />

      <View style={s.body}>
        <Text style={s.intro}>
          Tell Recall what a strong job looks like. My Job will search on your schedule and only
          keep the best verified matches.
        </Text>

        <Text style={s.sectionTitle}>What you want</Text>
        <Text style={s.label}>Target roles</Text>
        <TextInput
          style={s.input}
          value={roles}
          onChangeText={setRoles}
          placeholder="Backend Engineer, Platform Engineer"
          placeholderTextColor={C.textDisabled}
          autoCapitalize="words"
        />
        <Text style={s.help}>Separate multiple roles with commas.</Text>

        <Text style={s.label}>Skills to prioritize</Text>
        <TextInput
          style={s.input}
          value={skills}
          onChangeText={setSkills}
          placeholder="Python, FastAPI, APIs, AWS"
          placeholderTextColor={C.textDisabled}
        />

        <Text style={s.label}>Location</Text>
        <TextInput
          style={s.input}
          value={location}
          onChangeText={setLocation}
          placeholder="Remote in the United States"
          placeholderTextColor={C.textDisabled}
        />

        <Text style={s.label}>Work style</Text>
        <View style={s.chipRow}>
          {(["remote", "hybrid", "onsite"] as const).map((value) => (
            <Chip
              key={value}
              value={value}
              label={{ remote: "Remote", hybrid: "Hybrid", onsite: "On-site" }[value]}
              selected={workModes.includes(value)}
              onPress={(next) => toggle(next, workModes, setWorkModes)}
            />
          ))}
        </View>

        <Text style={s.label}>Experience level</Text>
        <View style={s.chipRow}>
          {(["internship", "entry", "mid", "senior"] as const).map((value) => (
            <Chip
              key={value}
              value={value}
              label={{ internship: "Internship", entry: "Entry / L3", mid: "Mid-level", senior: "Senior" }[value]}
              selected={levels.includes(value)}
              onPress={(next) => toggle(next, levels, setLevels)}
            />
          ))}
        </View>

        <Text style={s.label}>Minimum salary (optional)</Text>
        <TextInput
          style={s.input}
          value={salary}
          onChangeText={setSalary}
          placeholder="100000"
          placeholderTextColor={C.textDisabled}
          keyboardType="number-pad"
        />

        <Text style={s.label}>Sponsorship</Text>
        <View style={s.chipRow}>
          <Chip value="unknown" label="Not specified" selected={sponsorship == null} onPress={() => setSponsorship(null)} />
          <Chip value="no" label="Not needed" selected={sponsorship === false} onPress={() => setSponsorship(false)} />
          <Chip value="yes" label="Required" selected={sponsorship === true} onPress={() => setSponsorship(true)} />
        </View>

        <Text style={s.sectionTitle}>Your background</Text>
        <Pressable
          style={({ pressed }) => [s.resumeButton, pressed && s.pressed]}
          onPress={() => void chooseResume()}
          disabled={uploadingResume}
        >
          <View style={s.resumeIcon}>
            <Icon name={resumeName ? "document-text" : "cloud-upload-outline"} size={22} color={C.primary} />
          </View>
          <View style={s.resumeCopy}>
            <Text style={s.resumeTitle} numberOfLines={1}>
              {uploadingResume ? "Uploading resume…" : resumeName ?? "Upload your resume"}
            </Text>
            <Text style={s.resumeMeta}>PDF, DOCX, or text · used only to improve matching</Text>
          </View>
          <Icon name="chevron-forward" size={18} color={C.textTertiary} />
        </Pressable>
        {resumeName ? (
          <Pressable
            onPress={() => {
              setResumeId(null);
              setResumeName(null);
            }}
          >
            <Text style={s.removeResume}>Remove resume</Text>
          </Pressable>
        ) : null}

        <Text style={s.label}>Anything else Recall should know?</Text>
        <TextInput
          style={[s.input, s.multiline]}
          value={background}
          onChangeText={setBackground}
          placeholder="Describe relevant experience, projects, work authorization, or industries you prefer."
          placeholderTextColor={C.textDisabled}
          multiline
          textAlignVertical="top"
          maxLength={6000}
        />

        <Text style={s.label}>Companies to avoid</Text>
        <TextInput
          style={s.input}
          value={excluded}
          onChangeText={setExcluded}
          placeholder="Optional — separate with commas"
          placeholderTextColor={C.textDisabled}
        />

        <Text style={s.sectionTitle}>Delivery</Text>
        <Text style={s.label}>Jobs per delivery</Text>
        <View style={s.chipRow}>
          {([5, 10, 15] as const).map((value) => (
            <Chip
              key={value}
              value={String(value)}
              label={!isPro && value > 5 ? `${value} · Pro` : String(value)}
              selected={count === value}
              onPress={() => setCount(value)}
              disabled={!isPro && value > 5}
            />
          ))}
        </View>

        <Text style={s.label}>How often</Text>
        <View style={s.chipRow}>
          {(["daily", "weekdays", "weekly", "monthly"] as const).map((value) => (
            <Chip
              key={value}
              value={value}
              label={
                {
                  daily: "Daily",
                  weekdays: "Weekdays",
                  weekly: "Weekly",
                  monthly: "Monthly",
                }[value] + (!isPro && value !== "weekly" ? " · Pro" : "")
              }
              selected={frequency === value}
              onPress={setFrequency}
              disabled={!isPro && value !== "weekly"}
            />
          ))}
        </View>
        {!isPro ? <Text style={s.help}>Free includes up to 5 matches each week.</Text> : null}

        <Text style={s.label}>First delivery</Text>
        {Platform.OS === "ios" && showPicker ? (
          <View style={s.pickerWrap}>
            <ReminderDateTimePicker value={nextRunAt} onChange={onPickerChange} disabled={busy} />
          </View>
        ) : (
          <Pressable
            style={({ pressed }) => [s.timeButton, pressed && s.pressed]}
            onPress={() => {
              Keyboard.dismiss();
              setShowPicker(true);
            }}
          >
            <Icon name="calendar-outline" size={20} color={C.primary} />
            <Text style={s.timeText}>{timeLabel}</Text>
          </Pressable>
        )}
        {Platform.OS === "android" && showPicker ? (
          <ReminderDateTimePicker value={nextRunAt} onChange={onPickerChange} disabled={busy} />
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
      paddingHorizontal: 0,
      paddingTop: 0,
    },
    body: { padding: Space.md, paddingBottom: Space.xl, gap: Space.xs },
    intro: { ...Type.secondary, color: C.textSecondary, lineHeight: 21, marginBottom: Space.md },
    sectionTitle: {
      ...Type.title,
      color: C.text,
      marginTop: Space.lg,
      marginBottom: Space.sm,
    },
    label: { ...Type.label, color: C.text, marginTop: Space.md, marginBottom: Space.xxs },
    help: { ...Type.caption, color: C.textTertiary, marginTop: Space.xxs },
    input: {
      ...Type.body,
      color: C.text,
      backgroundColor: C.surface,
      borderRadius: Radius.lg,
      minHeight: 52,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
    },
    multiline: { minHeight: 112 },
    chipRow: { flexDirection: "row", flexWrap: "wrap", gap: Space.xs },
    chip: {
      minHeight: 42,
      justifyContent: "center",
      paddingHorizontal: Space.md,
      borderRadius: Radius.full,
      backgroundColor: C.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
    },
    chipSelected: { backgroundColor: C.primaryLight, borderColor: C.primary },
    chipText: { ...Type.secondary, color: C.textSecondary, fontWeight: "600" },
    chipTextSelected: { color: C.primary },
    pressed: { opacity: 0.7 },
    disabled: { opacity: 0.4 },
    resumeButton: {
      minHeight: 72,
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      backgroundColor: C.surface,
      borderRadius: Radius.xl,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
    },
    resumeIcon: {
      width: 42,
      height: 42,
      borderRadius: 21,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.primaryLight,
    },
    resumeCopy: { flex: 1 },
    resumeTitle: { ...Type.body, color: C.text, fontWeight: "600" },
    resumeMeta: { ...Type.caption, color: C.textTertiary, marginTop: 2 },
    removeResume: { ...Type.secondary, color: C.danger, alignSelf: "flex-start", paddingVertical: Space.xs },
    timeButton: {
      minHeight: 52,
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      paddingHorizontal: Space.md,
      backgroundColor: C.surface,
      borderRadius: Radius.lg,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
    },
    timeText: { ...Type.body, color: C.text, flex: 1 },
    pickerWrap: { backgroundColor: C.surface, borderRadius: Radius.xl, overflow: "hidden" },
  });
}
