/**
 * Plans as the app sees them. The server decides what a plan includes
 * (`user.features`) and refuses anything else; these helpers only choose
 * what to show. Display names live in i18n (`plans.<id>`), never in code.
 */

export type PlanId = "free" | "pro";
export type PaidPlanId = Exclude<PlanId, "free">;

export type PlanFeature =
  | "all_models"
  | "image_generation"
  | "speech_transcription"
  | "speech_tts"
  | "live_talk";

type PlanHolder = { plan?: string | null; features?: readonly string[] | null } | null | undefined;

export function planOf(holder: PlanHolder): PlanId {
  const plan = holder?.plan;
  return plan === "pro" ? "pro" : "free";
}

/** Before the server lists features (an older cached user), assume the defaults. */
function fallbackFeatures(plan: PlanId): PlanFeature[] {
  if (plan === "free") return ["image_generation"];
  return ["all_models", "image_generation", "speech_transcription", "speech_tts", "live_talk"];
}

export function hasPlanFeature(holder: PlanHolder, feature: PlanFeature): boolean {
  const features = holder?.features;
  if (Array.isArray(features)) return features.includes(feature);
  return fallbackFeatures(planOf(holder)).includes(feature);
}

/** The plan to offer: Free sees the one paid plan, which sees none. */
export function upgradeTargets(current: PlanId): PaidPlanId[] {
  return current === "free" ? ["pro"] : [];
}

export function planNameKey(plan: PlanId): `plans.${PlanId}` {
  return `plans.${plan}`;
}

