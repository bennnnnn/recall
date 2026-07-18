import i18n from "@/lib/i18n";
import { instantHomePlaceholder, loadHomeFallback, localGreeting } from "@/lib/homeFallback";

jest.mock("@/lib/api", () => ({
  api: {
    listSuggestions: jest.fn().mockResolvedValue([
      {
        id: "sug-1",
        text: "Follow up on your React project",
        category: "project",
        source: "llm",
        created_at: "2026-01-01T00:00:00Z",
      },
    ]),
  },
}));

describe("instantHomePlaceholder", () => {
  beforeAll(async () => {
    await i18n.init({
      lng: "en",
      resources: {
        en: {
          translation: {
            "chat.home.greeting_morning": "Good morning",
            "chat.home.greeting_afternoon": "Good afternoon",
            "chat.home.greeting_evening": "Good evening",
            "chat.home.greeting_night": "Hey there",
            "chat.home.starter_plan_day": "Plan my day",
            "chat.home.starter_plan_day_prompt": "plan",
            "chat.home.starter_working_on": "Working on",
            "chat.home.starter_working_on_prompt": "work",
            "chat.home.starter_reflect": "Reflect",
            "chat.home.starter_reflect_prompt": "reflect",
            "chat.home.starter_quick_thought": "Quick thought",
            "chat.home.starter_quick_thought_prompt": "thought",
          },
        },
      },
    });
  });

  it("returns a sync greeting and time starter without network", () => {
    const screen = instantHomePlaceholder(new Date("2026-07-17T09:00:00"));
    expect(screen.greeting).toBe("Good morning");
    expect(screen.starters.length).toBeGreaterThan(0);
    expect(screen.project_highlight).toBeNull();
  });

  it("localGreeting buckets by hour", () => {
    expect(localGreeting(new Date("2026-07-17T09:00:00"))).toBe("Good morning");
    expect(localGreeting(new Date("2026-07-17T14:00:00"))).toBe("Good afternoon");
    expect(localGreeting(new Date("2026-07-17T19:00:00"))).toBe("Good evening");
    expect(localGreeting(new Date("2026-07-17T23:00:00"))).toBe("Hey there");
  });
});

describe("loadHomeFallback", () => {
  beforeAll(async () => {
    await i18n.init({ lng: "en", resources: { en: { translation: {} } } });
  });

  it("returns localized greeting and suggestion ids for dismiss", async () => {
    const screen = await loadHomeFallback("token");
    expect(screen.greeting.length).toBeGreaterThan(0);
    expect(screen.starters.some((s) => s.id === "sug-1")).toBe(true);
    expect(screen.starters.some((s) => s.kind === "time")).toBe(true);
  });

  it("filters internal suggestion phrasing", async () => {
    const { api } = jest.requireMock<{ api: { listSuggestions: jest.Mock } }>(
      "@/lib/api",
    );
    api.listSuggestions.mockResolvedValueOnce([
      {
        id: "bad",
        text: "The user prefers dark mode",
        category: "memory",
        source: "llm",
        created_at: "2026-01-01T00:00:00Z",
      },
    ]);
    const screen = await loadHomeFallback("token");
    expect(screen.starters.every((s) => s.id !== "bad")).toBe(true);
  });
});
