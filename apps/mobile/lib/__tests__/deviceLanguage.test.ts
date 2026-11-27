import { firstSupportedLanguage } from "@/lib/i18n/deviceLanguage";
import es from "@/lib/i18n/es.json";
import fr from "@/lib/i18n/fr.json";

type I18nModule = typeof import("@/lib/i18n");

/** A fresh launch of the i18n module on a phone whose languages are `locales`, in its order. */
function launchOn(locales: { languageCode: string | null; languageTag: string }[] | null): I18nModule {
  let launched: I18nModule | undefined;
  jest.isolateModules(() => {
    jest.doMock("expo-modules-core", () => ({
      requireOptionalNativeModule: () => (locales ? { getLocales: () => locales } : null),
    }));
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- a fresh copy per phone
    launched = require("@/lib/i18n") as I18nModule;
  });
  jest.dontMock("expo-modules-core");
  if (!launched) throw new Error("i18n did not load");
  return launched;
}

const french = { languageCode: "fr", languageTag: "fr-FR" };
const spanish = { languageCode: "es", languageTag: "es-MX" };
const german = { languageCode: "de", languageTag: "de-DE" };
const japanese = { languageCode: "ja", languageTag: "ja-JP" };

describe("firstSupportedLanguage", () => {
  it.each([
    [[french], "fr"],
    [[spanish], "es"],
    [[{ languageCode: "pt", languageTag: "pt-BR" }], "pt"],
    // The first language Recall has strings for, in the phone's order.
    [[german, spanish, french], "es"],
    [[{ languageCode: null, languageTag: "ru-RU" }], "ru"],
    [[{ languageCode: "TR", languageTag: "tr-TR" }], "tr"],
    [[german, japanese], "en"],
    [[], "en"],
  ])("reads %j as %s", (locales, code) => {
    expect(firstSupportedLanguage(locales)).toBe(code);
  });
});

describe("the launch language", () => {
  it("starts a French phone in French, before anyone signs in", () => {
    const { default: i18n } = launchOn([french]);
    expect(i18n.language).toBe("fr");
    expect(i18n.t("login.agree_line")).toBe(fr["login.agree_line"]);
  });

  it("starts a Spanish phone in Spanish", () => {
    const { default: i18n } = launchOn([spanish]);
    expect(i18n.language).toBe("es");
    expect(i18n.t("common.retry")).toBe(es["common.retry"]);
  });

  it("starts in English on a phone whose languages Recall does not have", () => {
    const { default: i18n } = launchOn([german, japanese]);
    expect(i18n.language).toBe("en");
    expect(i18n.hasResourceBundle("de", "translation")).toBe(false);
  });

  it("starts in English on a build that cannot read the phone's languages", () => {
    expect(launchOn(null).default.language).toBe("en");
  });

  it("gives way to the language the user chose, saved or on the profile", async () => {
    const { default: i18n, startLocale, ensureLocale } = launchOn([french]);
    // The cached account's language, before the first frame (lib/launchPrefs.ts).
    startLocale("en");
    expect(i18n.language).toBe("en");
    // The profile's, once /auth/me answers (contexts/AuthContext.tsx).
    await ensureLocale("es");
    expect(i18n.language).toBe("es");
  });
});
