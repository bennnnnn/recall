/**
 * Single source of truth for supported UI languages.
 *
 * To add a language: drop a `<code>.json` next to this file (mirror `en.json`'s
 * keys), import it in `index.ts`'s `resources`, and add one entry here. Missing
 * keys fall back to English automatically, so partial translations are safe.
 */
export type LanguageMeta = {
  code: string;
  /** Endonym — shown in its own language. */
  label: string;
  /** Right-to-left script (needs RTL layout work beyond strings). */
  rtl?: boolean;
};

export const LANGUAGES: LanguageMeta[] = [
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
  { code: "fr", label: "Français" },
  { code: "de", label: "Deutsch" },
  { code: "it", label: "Italiano" },
  { code: "pt", label: "Português" },
  { code: "ru", label: "Русский" },
  { code: "tr", label: "Türkçe" },
  { code: "am", label: "አማርኛ" },
];
