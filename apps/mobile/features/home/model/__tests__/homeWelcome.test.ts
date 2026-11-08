import i18n from "@/lib/i18n";
import { homeGreeting } from "@/features/home/model/homeWelcome";
import en from "@/lib/i18n/en.json";
import fr from "@/lib/i18n/fr.json";

const HOUR = 60 * 60 * 1000;

/** Local midnight of a day in July 2026, plus `day` days and `hour` hours. */
function at(day: number, hour: number, minute = 0): Date {
  return new Date(2026, 6, 17 + day, hour, minute);
}

const question = (now: Date) => homeGreeting(null, now).question;

describe("homeGreeting", () => {
  beforeAll(async () => {
    await i18n.init({ lng: "en", resources: { en: { translation: en }, fr: { translation: fr } } });
  });

  afterEach(async () => {
    await i18n.changeLanguage("en");
  });

  it("keeps one question for four hours, so reopening the home reads the same", () => {
    expect(question(at(0, 8))).toBe(question(at(0, 11, 59)));
    expect(question(at(0, 12))).toBe(question(at(0, 15, 59)));
    expect(question(at(0, 11, 59))).not.toBe(question(at(0, 12)));
  });

  it("changes through the day, and each day starts one question further on", () => {
    const day = [0, 4, 8, 12, 16, 20].map((hour) => question(at(0, hour)));
    expect(new Set(day).size).toBe(6);
    // At the same hour, a week asks every one of the seven questions.
    const week = Array.from({ length: 7 }, (_, d) => question(at(d, 9)));
    expect(new Set(week).size).toBe(7);
    for (const asked of week) expect(asked).toMatch(/\?$/);
  });

  it("turns at the phone's own 04:00, whatever its offset", () => {
    // Kolkata, UTC+5:30: its 04:00 is 22:30 UTC the day before. A slot counted in UTC
    // would turn at 05:30 there, mid-morning in a slot of its own.
    const offset = jest.spyOn(Date.prototype, "getTimezoneOffset").mockReturnValue(-330);
    try {
      const utc = (iso: string) => question(new Date(iso));
      expect(utc("2026-07-16T22:29:00Z")).not.toBe(utc("2026-07-16T22:30:00Z"));
      expect(utc("2026-07-16T22:30:00Z")).toBe(utc("2026-07-17T02:29:00Z"));
      expect(utc("2026-07-17T02:29:00Z")).not.toBe(utc("2026-07-17T02:30:00Z"));
    } finally {
      offset.mockRestore();
    }
  });

  it("says hi by the first name, or hi there without one", () => {
    const now = at(0, 9);
    expect(homeGreeting("  bini  Lee ", now).hello).toBe("Hi, Bini");
    expect(homeGreeting("", now).hello).toBe("Hi there");
    expect(homeGreeting(null, now).hello).toBe("Hi there");
    // The question never repeats the name: the hello holds it.
    for (let h = 0; h < 7 * 24; h += 4) {
      expect(homeGreeting("Bini", new Date(at(0, 0).getTime() + h * HOUR)).question).not.toContain("Bini");
    }
  });

  it("capitalises the name's first letter and keeps the rest as written", () => {
    const now = at(0, 9);
    expect(homeGreeting("mcKenzie", now).hello).toBe("Hi, McKenzie");
    expect(homeGreeting("élodie", now).hello).toBe("Hi, Élodie");
  });

  it("speaks the phone's language, not the server's", async () => {
    await i18n.changeLanguage("fr");
    const questions = new Set(
      Object.entries(fr).filter(([key]) => key.startsWith("chat.home.question_")).map(([, value]) => value),
    );
    expect(questions.size).toBe(7);
    for (let h = 0; h < 7 * 24; h += 4) {
      const greeting = homeGreeting("Sam", new Date(at(0, 0).getTime() + h * HOUR));
      expect(greeting.hello).toBe("Bonjour, Sam");
      expect(questions).toContain(greeting.question);
    }
  });
});
