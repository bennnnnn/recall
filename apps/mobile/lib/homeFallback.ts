import i18n from "@/lib/i18n";
import { api, type HomeScreen, type HomeStarter } from "@/lib/api";

function looksInternal(text: string): boolean {
  const clean = text.trim();
  if (!clean) return true;
  return /^(?:the\s+)?user(?:'s|\s+is|\s+has|\s+name\s+is|\s+prefers|\s+likes|\s+wants)\b/i.test(
    clean,
  );
}

export function localGreeting(now: Date = new Date()): string {
  const hour = now.getHours();
  if (hour >= 5 && hour < 12) return i18n.t("chat.home.greeting_morning");
  if (hour >= 12 && hour < 17) return i18n.t("chat.home.greeting_afternoon");
  if (hour >= 17 && hour < 22) return i18n.t("chat.home.greeting_evening");
  return i18n.t("chat.home.greeting_night");
}

/** First paint / empty-account chips — no assumed day history. */
export function welcomeStarters(): HomeStarter[] {
  return [
    {
      text: i18n.t("chat.home.starter_help_think"),
      prompt: i18n.t("chat.home.starter_help_think_prompt"),
      kind: "general",
    },
    {
      text: i18n.t("chat.home.starter_what_can_you"),
      prompt: i18n.t("chat.home.starter_what_can_you_prompt"),
      kind: "general",
    },
  ];
}

/** Sync placeholder so post-login home never paints a bare spinner. */
export function instantHomePlaceholder(now: Date = new Date()): HomeScreen {
  return {
    greeting: localGreeting(now),
    subtitle: null,
    project_highlight: null,
    urgent_todos: [],
    starters: welcomeStarters(),
  };
}

export async function loadHomeFallback(token: string): Promise<HomeScreen> {
  const starters: HomeStarter[] = [...welcomeStarters()];

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
