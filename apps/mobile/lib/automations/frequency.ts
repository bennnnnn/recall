import type { AutomationFrequency } from "@/lib/api/types";

/** Pure i18n-key mapping for an automation's frequency — kept in `lib/` (no
 * RN/component deps) so it can be shared by both the picker component and
 * plain-function modules like `lib/automations/schedule.ts`. */
export function automationFrequencyMessageKey(
  frequency: AutomationFrequency,
): `automations.frequency_${AutomationFrequency}` {
  return `automations.frequency_${frequency}`;
}
