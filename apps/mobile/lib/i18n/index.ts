import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./en.json";

type LocaleBundle = typeof en;

const LOCALE_LOADERS: Record<string, () => Promise<{ default: LocaleBundle }>> = {
  es: () => import("./es.json"),
  fr: () => import("./fr.json"),
  de: () => import("./de.json"),
  it: () => import("./it.json"),
  pt: () => import("./pt.json"),
  ru: () => import("./ru.json"),
  tr: () => import("./tr.json"),
  am: () => import("./am.json"),
};

const loadedLocales = new Set<string>(["en"]);

/** Boot English only. Other locales load when the user preference is not `en`. */
export async function ensureLocale(lng: string): Promise<void> {
  const code = lng.trim() || "en";
  if (code === "en") {
    await i18n.changeLanguage("en");
    return;
  }
  if (!loadedLocales.has(code)) {
    const load = LOCALE_LOADERS[code];
    if (!load) {
      await i18n.changeLanguage("en");
      return;
    }
    const mod = await load();
    i18n.addResourceBundle(code, "translation", mod.default, true, true);
    loadedLocales.add(code);
  }
  await i18n.changeLanguage(code);
}

i18n.use(initReactI18next).init({
  resources: { en: { translation: en } },
  lng: "en",
  fallbackLng: {
    de: ["en"],
    es: ["en"],
    fr: ["en"],
    it: ["en"],
    pt: ["en"],
    ru: ["en"],
    tr: ["en"],
    am: ["en"],
    default: ["en"],
  },
  interpolation: { escapeValue: false },
});

export { LEARNING_LANGUAGES, LANGUAGES } from "./languages";
export type { LanguageMeta } from "./languages";
export default i18n;
