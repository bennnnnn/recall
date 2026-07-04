import i18n from "@/lib/i18n";
import { api, type HomeScreen, type HomeStarter } from "@/lib/api";

const MORNING_START = 5;
const CALENDAR_TODAY_END = 12;
const REFLECT_START = 15;

function looksInternal(text: string): boolean {
  const clean = text.trim();
  if (!clean) return true;
  return /^(?:the\s+)?user(?:'s|\s+is|\s+has|\s+name\s+is|\s+prefers|\s+likes|\s+wants)\b/i.test(
    clean,
  );
}

function localGreeting(): string {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return i18n.t("chat.home.greeting_morning");
  if (hour >= 12 && hour < 17) return i18n.t("chat.home.greeting_afternoon");
  if (hour >= 17 && hour < 22) return i18n.t("chat.home.greeting_evening");
  return i18n.t("chat.home.greeting_night");
}

function timeStarters(): HomeStarter[] {
  const hour = new Date().getHours();
  if (hour >= MORNING_START && hour < CALENDAR_TODAY_END) {
    return [
      {
        text: i18n.t("chat.home.starter_plan_day"),
        prompt: i18n.t("chat.home.starter_plan_day_prompt"),
        kind: "time",
      },
    ];
  }
  if (hour >= CALENDAR_TODAY_END && hour < REFLECT_START) {
    return [
      {
        text: i18n.t("chat.home.starter_working_on"),
        prompt: i18n.t("chat.home.starter_working_on_prompt"),
        kind: "time",
      },
    ];
  }
  if (hour >= REFLECT_START && hour < 22) {
    return [
      {
        text: i18n.t("chat.home.starter_reflect"),
        prompt: i18n.t("chat.home.starter_reflect_prompt"),
        kind: "time",
      },
    ];
  }
  return [
    {
      text: i18n.t("chat.home.starter_quick_thought"),
      prompt: i18n.t("chat.home.starter_quick_thought_prompt"),
      kind: "time",
    },
  ];
}

export async function loadHomeFallback(token: string): Promise<HomeScreen> {
  const starters: HomeStarter[] = [...timeStarters()];

  const suggestions = await api.listSuggestions(token).catch(() => []);
  for (const item of suggestions) {
    if (starters.length >= 5) break;
    if (looksInternal(item.text)) continue;
    const prompt = item.text;
    if (starters.some((s) => s.prompt === prompt)) continue;
    starters.push({
      id: item.id,
      text: item.text.slice(0, 48),
      prompt,
      kind: "general",
    });
  }

  if (starters.length === 0) {
    starters.push({
      text: i18n.t("chat.home.starter_help_think"),
      prompt: i18n.t("chat.home.starter_help_think_prompt"),
      kind: "general",
    });
  }

  return {
    greeting: localGreeting(),
    subtitle: null,
    project_highlight: null,
    urgent_todos: [],
    starters,
  };
}
