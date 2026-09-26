import type { ComponentProps } from "react";
import type { TFunction } from "i18next";

import type { Icon } from "@/ui/icons/Icon";
import type { JobSearchProfile } from "@/lib/api";

export type SearchField = {
  key: string;
  icon: ComponentProps<typeof Icon>["name"];
  label: string;
  values: string[];
};

/** Short "Sat, Sep 19, 8:00 AM" label for the next scheduled run ("" if unset). */
export function nextDeliveryDate(profile: JobSearchProfile): string {
  const date = new Date(profile.next_run_at);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/**
 * Labeled field rows describing a My Job search profile — only fields that are
 * set. Each field is a caption label plus one value chip per value, so the
 * dashboard card reads as structured data instead of a pile of tags.
 */
export function searchProfileFields(profile: JobSearchProfile, t: TFunction): SearchField[] {
  const fields: SearchField[] = [];
  if (profile.location) {
    fields.push({
      key: "location",
      icon: "map-pin",
      label: t("my_job.location_label"),
      values: [profile.location],
    });
  }
  if (profile.work_modes.length > 0) {
    fields.push({
      key: "work_mode",
      icon: "laptop",
      label: t("my_job.work_mode_label"),
      values: profile.work_modes.map((mode) => t(`my_job.work_${mode}`)),
    });
  }
  if (profile.experience_levels.length > 0) {
    fields.push({
      key: "experience",
      icon: "bar-chart",
      label: t("my_job.experience_label"),
      values: profile.experience_levels.map((level) => t(`my_job.level_${level}`)),
    });
  }
  if (profile.salary_min != null) {
    fields.push({
      key: "salary",
      icon: "banknote",
      label: t("my_job.salary_label"),
      values: [t("my_job.salary_min_chip", { amount: profile.salary_min.toLocaleString() })],
    });
  }
  fields.push({
    key: "count",
    icon: "briefcase",
    label: t("my_job.count_label"),
    values: [`${profile.result_count} ${t("my_job.count_jobs")}`],
  });
  fields.push({
    key: "frequency",
    icon: "repeat",
    label: t("my_job.frequency_label"),
    values: [t(`my_job.freq_${profile.frequency}`)],
  });
  const next = nextDeliveryDate(profile);
  if (next) {
    fields.push({
      key: "next",
      icon: "clock",
      label: t("my_job.field_next_delivery"),
      values: [next],
    });
  }
  return fields;
}
