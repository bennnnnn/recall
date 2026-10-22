import {
  DOCUMENT_GROUPS,
  STANDARD_DOCUMENT_KEYS,
} from "@/features/memory/model/memoryDocuments";
import i18n, { ensureLocale, startLocale } from "@/lib/i18n";
import en from "@/lib/i18n/en.json";
import am from "@/lib/i18n/am.json";
import de from "@/lib/i18n/de.json";
import es from "@/lib/i18n/es.json";
import fr from "@/lib/i18n/fr.json";
import itLocale from "@/lib/i18n/it.json";
import pt from "@/lib/i18n/pt.json";
import ru from "@/lib/i18n/ru.json";
import tr from "@/lib/i18n/tr.json";

const LOCALES = { am, de, es, fr, it: itLocale, pt, ru, tr } as const;
const EN_KEYS = Object.keys(en).sort();

describe("i18n locale files", () => {
  for (const [code, bundle] of Object.entries(LOCALES)) {
    it(`${code}.json has every en.json key`, () => {
      const keys = Object.keys(bundle).sort();
      const missing = EN_KEYS.filter((k) => !keys.includes(k));
      const extra = keys.filter((k) => !EN_KEYS.includes(k));
      expect(missing).toEqual([]);
      expect(extra).toEqual([]);
    });
  }
});

describe("i18n runtime", () => {
  it("boots with English only", () => {
    expect(i18n.hasResourceBundle("en", "translation")).toBe(true);
    expect(i18n.hasResourceBundle("es", "translation")).toBe(false);
  });

  it("resolves every English key to its own text", async () => {
    await ensureLocale("en");
    const wrong = Object.entries(en)
      .filter(([, value]) => typeof value === "string" && !value.includes("{{"))
      .filter(([key, value]) => i18n.t(key) !== value)
      .map(([key]) => key);
    expect(wrong).toEqual([]);
  });

  it("resolves the memory page words the app builds from server keys", async () => {
    await ensureLocale("en");
    const keys = [
      ...STANDARD_DOCUMENT_KEYS.flatMap((key) => [
        `memory.doc.${key}.title`,
        `memory.doc.${key}.summary`,
      ]),
      ...DOCUMENT_GROUPS.map((group) => `memory.group.${group}`),
    ];
    // A key that falls through comes back unchanged.
    expect(keys.filter((key) => i18n.t(key) === key)).toEqual([]);
  });

  it("loads a locale on demand and falls back for unknown codes", async () => {
    await ensureLocale("es");
    expect(i18n.hasResourceBundle("es", "translation")).toBe(true);
    expect(i18n.language).toBe("es");

    await ensureLocale("not-a-locale");
    expect(i18n.language).toBe("en");
  });

  it("switches to the launch language at once, before anything renders", () => {
    startLocale("fr");
    // No await: the first frame reads it synchronously.
    expect(i18n.language).toBe("fr");
    expect(i18n.t("common.retry")).toBe(fr["common.retry"]);

    startLocale("not-a-locale");
    expect(i18n.language).toBe("en");
  });

  it("does not announce a change to the language already in use", async () => {
    const changed = jest.fn();
    i18n.on("languageChanged", changed);
    await ensureLocale("en");
    expect(changed).not.toHaveBeenCalled();
    await ensureLocale("de");
    expect(changed).toHaveBeenCalledWith("de");
    i18n.off("languageChanged", changed);
    await ensureLocale("en");
  });
});
