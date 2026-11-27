import am from "@/lib/i18n/am.json";
import en from "@/lib/i18n/en.json";
import es from "@/lib/i18n/es.json";
import fr from "@/lib/i18n/fr.json";
import hi from "@/lib/i18n/hi.json";
import pt from "@/lib/i18n/pt.json";
import ru from "@/lib/i18n/ru.json";
import tr from "@/lib/i18n/tr.json";

const LOCALES = { en, es, fr, pt, ru, tr, am, hi } as const;

// The sign-in tap is the account's AI-data consent (features/auth/api.ts), so the line under
// the buttons says what it agrees to: outside AI and search services answer the user's
// messages, files and voice, and the Terms and Privacy Policy (App Store 5.1.2(i)). The owner
// kept the shorter Terms-only line on 2026-11-06 and approved this change on 2026-11-27.
it("says continuing agrees to the outside AI services and to the Terms and Privacy Policy", () => {
  expect(en["login.agree_line"]).toBe(
    "By continuing, you agree that your messages, files and voice are answered by outside AI " +
      "and search services, such as OpenAI and Anthropic through OpenRouter, and to the " +
      "<terms>Terms</terms> and <privacy>Privacy Policy</privacy>.",
  );
});

it.each(Object.entries(LOCALES))(
  "%s names the services and links the Terms and Privacy Policy",
  (_code, strings) => {
    const line = strings["login.agree_line"];
    for (const name of ["OpenAI", "Anthropic", "OpenRouter"]) expect(line).toContain(name);
    expect(line).toMatch(/<terms>[^<]+<\/terms>/);
    expect(line).toMatch(/<privacy>[^<]+<\/privacy>/);
  },
);
