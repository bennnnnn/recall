import i18n from "@/lib/i18n";
import {
  instantHomePlaceholder,
  loadHomeFallback,
  localGreeting,
  welcomeStarters,
} from "@/lib/homeFallback";

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

const EN = {
  "chat.home.greeting_morning": "Good morning",
  "chat.home.greeting_afternoon": "Good afternoon",
  "chat.home.greeting_evening": "Good evening",
  "chat.home.greeting_night": "Hey there",
  "chat.home.starter_help_think": "Help me think",
  "chat.home.starter_help_think_prompt": "think prompt",
  "chat.home.starter_what_can_you": "What can you do?",
  "chat.home.starter_what_can_you_prompt": "can do prompt",
};

describe("instantHomePlaceholder", () => {
  beforeAll(async () => {
    await i18n.init({
      lng: "en",
      resources: { en: { translation: EN } },
    });
  });

  it("uses welcome starters, not day-reflect time chips", () => {
    const screen = instantHomePlaceholder(new Date("2026-07-17T20:00:00"));
    expect(screen.greeting).toBe("Good evening");
    expect(screen.starters.map((s) => s.text)).toEqual([
      "Help me think",
      "What can you do?",
    ]);
    expect(screen.starters.every((s) => s.kind === "general")).toBe(true);
  });

  it("localGreeting buckets by hour", () => {
    expect(localGreeting(new Date("2026-07-17T09:00:00"))).toBe("Good morning");
    expect(localGreeting(new Date("2026-07-17T14:00:00"))).toBe("Good afternoon");
    expect(localGreeting(new Date("2026-07-17T19:00:00"))).toBe("Good evening");
    expect(localGreeting(new Date("2026-07-17T23:00:00"))).toBe("Hey there");
  });

  it("welcomeStarters stays free of plan/reflect copy", () => {
    const texts = welcomeStarters().map((s) => s.text).join(" ");
    expect(texts.toLowerCase()).not.toContain("today");
    expect(texts.toLowerCase()).not.toContain("tonight");
  });
});

describe("loadHomeFallback", () => {
  beforeAll(async () => {
    await i18n.init({
      lng: "en",
      resources: { en: { translation: EN } },
    });
  });

  it("returns localized greeting and suggestion ids for dismiss", async () => {
    const screen = await loadHomeFallback("token");
    expect(screen.greeting.length).toBeGreaterThan(0);
    expect(screen.starters.some((s) => s.id === "sug-1")).toBe(true);
    expect(screen.starters.some((s) => s.kind === "general")).toBe(true);
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
