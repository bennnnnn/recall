import i18n from "@/lib/i18n";
import { instantHomePlaceholder, localGreeting } from "@/features/home/model/homeWelcome";

const EN = {
  "chat.home.greeting_morning": "Good morning",
  "chat.home.greeting_afternoon": "Good afternoon",
  "chat.home.greeting_evening": "Good evening",
  "chat.home.greeting_night": "Hey there",
};

describe("instantHomePlaceholder", () => {
  beforeAll(async () => {
    await i18n.init({
      lng: "en",
      resources: { en: { translation: EN } },
    });
  });

  it("paints a greeting and no starter chips", () => {
    const screen = instantHomePlaceholder(new Date("2026-07-17T20:00:00"));
    expect(screen.greeting).toBe("Good evening");
    expect(screen.starters).toEqual([]);
  });

  it("localGreeting buckets by hour", () => {
    expect(localGreeting(new Date("2026-07-17T09:00:00"))).toBe("Good morning");
    expect(localGreeting(new Date("2026-07-17T14:00:00"))).toBe("Good afternoon");
    expect(localGreeting(new Date("2026-07-17T19:00:00"))).toBe("Good evening");
    expect(localGreeting(new Date("2026-07-17T23:00:00"))).toBe("Hey there");
  });
});
