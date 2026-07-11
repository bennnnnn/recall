/** Shared Learning progress tint (home card + Continue CTAs). */

const DAY_START_HOUR = 6;
const DAY_END_HOUR = 22;

/**
 * 0 = calm, 1 = strongest end-of-day urgency.
 * Goal met → 0. Incomplete → rises through the day, stronger when further behind.
 */
export function homeLearningUrgency(options: {
  completedToday: number;
  dailyGoal: number;
  hour: number;
}): number {
  const goal = Math.max(0, options.dailyGoal);
  if (goal <= 0) return 0;
  const done = Math.max(0, options.completedToday);
  if (done >= goal) return 0;

  const span = DAY_END_HOUR - DAY_START_HOUR;
  const t = Math.min(1, Math.max(0, (options.hour - DAY_START_HOUR) / span));
  // Ease in so mornings stay calm.
  const timeUrgency = t * t;
  const remaining = 1 - Math.min(1, done / goal);
  return Math.min(1, timeUrgency * (0.35 + 0.65 * remaining));
}

function parseHex(hex: string): [number, number, number] | null {
  const raw = hex.replace("#", "").trim();
  if (raw.length === 3) {
    const r = Number.parseInt(raw[0] + raw[0], 16);
    const g = Number.parseInt(raw[1] + raw[1], 16);
    const b = Number.parseInt(raw[2] + raw[2], 16);
    if ([r, g, b].some((n) => Number.isNaN(n))) return null;
    return [r, g, b];
  }
  if (raw.length !== 6) return null;
  const r = Number.parseInt(raw.slice(0, 2), 16);
  const g = Number.parseInt(raw.slice(2, 4), 16);
  const b = Number.parseInt(raw.slice(4, 6), 16);
  if ([r, g, b].some((n) => Number.isNaN(n))) return null;
  return [r, g, b];
}

/** Linear blend of two #RRGGBB colors. */
export function mixHexColors(from: string, to: string, amount: number): string {
  const a = parseHex(from);
  const b = parseHex(to);
  if (!a || !b) return from;
  const t = Math.min(1, Math.max(0, amount));
  const channel = (x: number, y: number) => Math.round(x + (y - x) * t);
  const r = channel(a[0], b[0]).toString(16).padStart(2, "0");
  const g = channel(a[1], b[1]).toString(16).padStart(2, "0");
  const bl = channel(a[2], b[2]).toString(16).padStart(2, "0");
  return `#${r}${g}${bl}`;
}

export type LearningProgressColors = {
  background: string;
  fill: string;
  track: string;
  /** Text, chevron, outline border — same urgency curve as the fill. */
  accent: string;
};

export function homeLearningCardColors(options: {
  urgency: number;
  surface: string;
  primaryLight: string;
  dangerLight: string;
  primary: string;
  danger: string;
  success: boolean;
}): LearningProgressColors {
  if (options.success) {
    return {
      background: options.primaryLight,
      fill: options.primary,
      track: options.surface,
      accent: options.primary,
    };
  }
  const u = Math.min(1, Math.max(0, options.urgency));
  const accent = mixHexColors(options.primary, options.danger, u * 0.85);
  return {
    background: mixHexColors(options.primaryLight, options.dangerLight, u),
    fill: accent,
    track: mixHexColors(options.surface, options.dangerLight, u * 0.4),
    accent,
  };
}

/** Resolve tint from today's progress + local hour (shared by home + CTAs). */
export function learningProgressColors(options: {
  completedToday: number;
  dailyGoal: number;
  hour?: number;
  surface: string;
  primaryLight: string;
  dangerLight: string;
  primary: string;
  danger: string;
}): LearningProgressColors {
  const hour = options.hour ?? new Date().getHours();
  const success =
    options.dailyGoal > 0 && options.completedToday >= options.dailyGoal;
  const urgency = homeLearningUrgency({
    completedToday: options.completedToday,
    dailyGoal: options.dailyGoal,
    hour,
  });
  return homeLearningCardColors({
    urgency,
    surface: options.surface,
    primaryLight: options.primaryLight,
    dangerLight: options.dangerLight,
    primary: options.primary,
    danger: options.danger,
    success,
  });
}
