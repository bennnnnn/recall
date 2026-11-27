/**
 * The phone's language: the first of its preferred languages that Recall has strings for,
 * English when none is. It is the language before anyone signs in, and a new account
 * starts in it (the sign-in sends it). A language the user chose wins over it: the one the
 * cached account last used (`lib/launchPrefs.ts`) and the profile's (`contexts/AuthContext.tsx`).
 */
import { readPhoneLocalization } from "@/lib/phoneLocalization";

import { LANGUAGES } from "./languages";

const SUPPORTED: ReadonlySet<string> = new Set(LANGUAGES.map((language) => language.code));

/** What this file reads of a locale expo-localization returns. */
type PhoneLocale = { languageCode?: string | null; languageTag?: string | null };

/** The first supported language among the phone's, in its order; "en" for none. */
export function firstSupportedLanguage(locales: readonly PhoneLocale[]): string {
  for (const locale of locales) {
    // languageCode is the primary subtag ("pt" for "pt-BR"); the tag stands in when absent.
    const code = (locale.languageCode || locale.languageTag?.split(/[-_]/)[0] || "")
      .trim()
      .toLowerCase();
    if (SUPPORTED.has(code)) return code;
  }
  return "en";
}

/** The phone's preferred languages, in its order; empty when this build cannot read them. */
function phoneLocales(): PhoneLocale[] {
  const locales: unknown = readPhoneLocalization((module) => module.getLocales(), []);
  return Array.isArray(locales) ? (locales as PhoneLocale[]) : [];
}

/** The phone's first supported language now ("en" when it has none or cannot say). */
export function deviceLanguage(): string {
  return firstSupportedLanguage(phoneLocales());
}
