import type { ComponentProps } from "react";
import type { TFunction } from "i18next";

import type { Icon } from "@/components/Icon";
import type { JobSearchProfile } from "@/lib/api";

export type SearchChip = {
  icon: ComponentProps<typeof Icon>["name"];
  label: string;
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

/** Icon chips describing a My Job search profile — only fields that are set. */
export function searchProfileChips(profile: JobSearchProfile, t: TFunction): SearchChip[] {
  const chips: SearchChip[] = [];
  if (profile.location) {
    chips.push({ icon: "location-outline", label: profile.location });
  }
  if (profile.work_modes.length > 0) {
    chips.push({
      icon: "laptop-outline",
      label: profile.work_modes.map((mode) => t(`my_job.work_${mode}`)).join(" / "),
    });
  }
  if (profile.experience_levels.length > 0) {
    chips.push({
      icon: "bar-chart-outline",
      label: profile.experience_levels.map((level) => t(`my_job.level_${level}`)).join(" / "),
    });
  }
  if (profile.salary_min != null) {
    chips.push({
      icon: "cash-outline",
      label: t("my_job.salary_min_chip", { amount: profile.salary_min.toLocaleString() }),
    });
  }
  chips.push({
    icon: "briefcase-outline",
    label: `${profile.result_count} ${t("my_job.count_jobs")}`,
  });
  chips.push({ icon: "repeat-outline", label: t(`my_job.freq_${profile.frequency}`) });
  const next = nextDeliveryDate(profile);
  if (next) {
    chips.push({ icon: "time-outline", label: t("my_job.next_delivery", { date: next }) });
  }
  return chips;
}
