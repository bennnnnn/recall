import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import { DATE_FORMAT_CHANGED } from "@/lib/datetime/format";
import { readMathSpeechWords, setMathSpeechWords } from "@/lib/math/speechWords";

import { deviceLanguage } from "./deviceLanguage";
import en from "./en.json";
import { installPluralRules } from "./pluralRules";
import type { Translate } from "./translate";

type LocaleBundle = typeof en;

// Each bundle is evaluated only when its language is first used. The require
// is synchronous so the launch language can be in place before the first frame.
const LOCALE_BUNDLES: Record<string, () => LocaleBundle> = {
  es: () => require("./es.json") as LocaleBundle,
  fr: () => require("./fr.json") as LocaleBundle,
  pt: () => require("./pt.json") as LocaleBundle,
  ru: () => require("./ru.json") as LocaleBundle,
  tr: () => require("./tr.json") as LocaleBundle,
  am: () => require("./am.json") as LocaleBundle,
  hi: () => require("./hi.json") as LocaleBundle,
};

const loadedLocales = new Set<string>(["en"]);

/** The supported code for a preference ("en" for unknown), its bundle added. */
function addLocale(lng: string): string {
  const code = lng.trim() || "en";
  if (loadedLocales.has(code)) return code;
  const bundle = LOCALE_BUNDLES[code];
  if (!bundle) return "en";
  i18n.addResourceBundle(code, "translation", bundle(), true, true);
  loadedLocales.add(code);
  return code;
}

/** Switches to `lng` ("en" for one Recall has no strings for), its bundle loaded first. */
export async function ensureLocale(lng: string): Promise<void> {
  const code = addLocale(lng);
  // Already in it (the launch language, say): a change event would re-render
  // every translated component for the same words.
  if (code === i18n.language) return;
  await i18n.changeLanguage(code);
}

/**
 * Before the first render: the language the cached account last used
 * (`lib/launchPrefs.ts`). The bundle is already in, so the switch takes
 * effect at once and the first frame is drawn in it.
 */
export function startLocale(lng: string): void {
  const code = addLocale(lng);
  if (code !== i18n.language) void i18n.changeLanguage(code);
}

// Before init: i18next reads the plural rules when it first counts.
installPluralRules();

// Formulas are spoken in the app's language (a screen reader's label, read-aloud).
i18n.on("languageChanged", (lng: string) => {
  const english = en as Record<string, string>;
  const word = (key: string): string => {
    const value: unknown = i18n.getResource(lng, "translation", key);
    return typeof value === "string" ? value : (english[key] ?? key);
  };
  setMathSpeechWords(readMathSpeechWords(word as Translate, lng));
});

// The phone's language until a choice replaces it: the cached account's, before the first
// render (`startLocale`), then the profile's. Only its bundle and English are loaded.
const phoneLanguage = deviceLanguage();
const launchBundle = LOCALE_BUNDLES[phoneLanguage] as (() => LocaleBundle) | undefined;
const LAUNCH_LANGUAGE = launchBundle ? phoneLanguage : "en";
const launchResources: Record<string, { translation: LocaleBundle }> = { en: { translation: en } };
if (launchBundle) {
  launchResources[LAUNCH_LANGUAGE] = { translation: launchBundle() };
  loadedLocales.add(LAUNCH_LANGUAGE);
}

i18n.use(initReactI18next).init({
  resources: launchResources,
  lng: LAUNCH_LANGUAGE,
  fallbackLng: {
    es: ["en"],
    fr: ["en"],
    pt: ["en"],
    ru: ["en"],
    tr: ["en"],
    am: ["en"],
    hi: ["en"],
    default: ["en"],
  },
  interpolation: { escapeValue: false },
  // A date follows the phone's zone and clock as it follows the language.
  react: { bindI18n: `languageChanged ${DATE_FORMAT_CHANGED}` },
});

export default i18n;
