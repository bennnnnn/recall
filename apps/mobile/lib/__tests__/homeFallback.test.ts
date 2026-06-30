import i18n from "@/lib/i18n";
import { loadHomeFallback } from "@/lib/homeFallback";

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
