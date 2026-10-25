/**
 * What the phone says about time: its zone and its 12/24-hour setting. `format.ts`
 * keeps what this reads and asks again when either may have changed.
 */
import type { Calendar } from "expo-localization";

export type HourCycle = "h12" | "h23";

export type PhoneClock = {
  /** The device's IANA zone; undefined when the engine cannot name it. */
  timeZone: string | undefined;
  hourCycle: HourCycle;
};

/** The parts of expo-localization's native module this file uses. */
type LocalizationModule = {
  getCalendars: () => Calendar[];
  addListener: (event: string, listener: () => void) => { remove: () => void };
};

let localization: LocalizationModule | null | undefined;

/**
 * expo-localization's native module, when this build has it. Read through
 * `requireOptionalNativeModule`: an over-the-air update can reach a binary built
 * before the module was added, and the package's own JS throws on import there.
 */
function loadLocalization(): LocalizationModule | null {
  if (localization !== undefined) return localization;
  try {
    const { requireOptionalNativeModule } =
      // eslint-disable-next-line @typescript-eslint/no-require-imports -- lazy: Node tests have no native modules
      require("expo-modules-core") as typeof import("expo-modules-core");
    localization = requireOptionalNativeModule<LocalizationModule>("ExpoLocalization");
  } catch {
    localization = null;
  }
  return localization;
}

/** The device's IANA zone ("America/New_York"), or undefined when the engine cannot name it. */
export function deviceTimeZone(): string | undefined {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
  } catch {
    return undefined;
  }
}

/**
 * Whether times read on a 24-hour clock in `locale` (the phone's when omitted): its
 * convention, not the phone's switch, which no engine's Intl sees.
 */
export function localeUses24HourClock(locale?: string): boolean {
  try {
    const options = new Intl.DateTimeFormat(locale, { hour: "numeric" }).resolvedOptions();
    if (options.hourCycle) return options.hourCycle === "h23" || options.hourCycle === "h24";
    if (typeof options.hour12 === "boolean") return !options.hour12;
  } catch {
    // Fall through to formatting a known afternoon hour.
  }
  try {
    const afternoon = new Intl.DateTimeFormat(locale, { hour: "numeric" }).format(new Date(2000, 0, 1, 13));
    return /13/.test(afternoon);
  } catch {
    return false;
  }
}

/** The phone's 24-Hour Time switch, or null when this build cannot read it. */
function phoneUses24HourClock(): boolean | null {
  try {
    return loadLocalization()?.getCalendars()[0]?.uses24hourClock ?? null;
  } catch {
    return null;
  }
}

/**
 * The zone and the hour cycle now. The hour cycle is the phone's setting (iOS reads
 * it from `Locale.current`, Android from `DateFormat.is24HourFormat`), which neither
 * engine's Intl sees; a build without the module falls back to the phone locale's
 * own clock, as the time picker read it before.
 */
export function readPhoneClock(): PhoneClock {
  const uses24 = phoneUses24HourClock() ?? localeUses24HourClock();
  return { timeZone: deviceTimeZone(), hourCycle: uses24 ? "h23" : "h12" };
}

/** Calls `listener` when the OS says the locale, the clock setting or the zone changed. */
export function onPhoneClockChange(listener: () => void): () => void {
  const module = loadLocalization();
  if (!module) return () => {};
  try {
    // iOS sends both on a locale change or a significant time change (a new zone,
    // midnight, daylight saving); Android sends both on a configuration change.
    const subscription = module.addListener("onCalendarSettingsChanged", listener);
    return () => subscription.remove();
  } catch {
    return () => {};
  }
}
