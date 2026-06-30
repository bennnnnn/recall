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
      expect(keys).toEqual(EN_KEYS);
    });
  }
});
