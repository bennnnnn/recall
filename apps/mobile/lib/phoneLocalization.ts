/**
 * expo-localization's native module, read in one place: the phone's languages
 * (`lib/i18n/deviceLanguage.ts`) and its clock (`lib/datetime/phoneClock.ts`).
 *
 * Loaded through `requireOptionalNativeModule`: an over-the-air update can reach a binary
 * built before the module was added, and the package's own JS throws on import there.
 * One failure rule for every reader: a build without the module, or a read that throws,
 * gives the reader's fallback, and the first failure is said once in the log.
 */
import type { Calendar, Locale } from "expo-localization";

/** The parts of the native module the app reads. */
type LocalizationModule = {
  getLocales: () => Locale[];
  getCalendars: () => Calendar[];
  addListener: (event: string, listener: () => void) => { remove: () => void };
};

let localization: LocalizationModule | null | undefined;
let failureSaid = false;

function sayFailure(error: unknown): void {
  if (failureSaid) return;
  failureSaid = true;
  console.warn("[localization] the phone's language and clock settings could not be read", error);
}

/** The module, loaded once; null when this build has none. */
function loadLocalization(): LocalizationModule | null {
  if (localization !== undefined) return localization;
  try {
    const { requireOptionalNativeModule } =
      // eslint-disable-next-line @typescript-eslint/no-require-imports -- lazy: Node tests have no native modules
      require("expo-modules-core") as typeof import("expo-modules-core");
    localization = requireOptionalNativeModule<LocalizationModule>("ExpoLocalization");
  } catch (error) {
    sayFailure(error);
    localization = null;
  }
  return localization;
}

/** What `read` gets from the module, or `fallback` when this build has none or the read throws. */
export function readPhoneLocalization<T>(read: (module: LocalizationModule) => T, fallback: T): T {
  const module = loadLocalization();
  if (!module) return fallback;
  try {
    return read(module);
  } catch (error) {
    sayFailure(error);
    return fallback;
  }
}
