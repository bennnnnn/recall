/**
 * Usage counts read as numbers do in each language (Settings → Usage showed "957 of 1000").
 * Rendered through the real i18next with the app's own strings, not a stand-in `t`.
 */
import i18next from "i18next";

import de from "@/lib/i18n/de.json";
import en from "@/lib/i18n/en.json";

async function renderer(lng: "en" | "de") {
  const i18n = i18next.createInstance();
  await i18n.init({
    lng,
    resources: { en: { translation: en }, de: { translation: de } },
    interpolation: { escapeValue: false },
  });
  return i18n;
}

it("groups the counts the way each language does", async () => {
  const english = await renderer("en");
  expect(english.t("settings.usage_messages_left", { left: 957, total: 1000 })).toBe(
    "957 of 1,000 messages left today",
  );
  expect(english.t("chat.quota_nudge_messages", { left: 3, total: 10 })).toContain("3 of 10");

  const german = await renderer("de");
  expect(german.t("settings.usage_messages_left", { left: 1000, total: 1000 })).toContain("1.000");
});
