import { api, type HomeScreen, type HomeStarter } from "@/lib/api";
import {
  instantHomePlaceholder,
  localGreeting,
  welcomeStarters,
} from "@/lib/homeWelcome";

export { instantHomePlaceholder, localGreeting, welcomeStarters } from "@/lib/homeWelcome";

function looksInternal(text: string): boolean {
  const clean = text.trim();
  if (!clean) return true;
  return /^(?:the\s+)?user(?:'s|\s+is|\s+has|\s+name\s+is|\s+prefers|\s+likes|\s+wants)\b/i.test(
    clean,
  );
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
    return instantHomePlaceholder();
  }

  return {
    greeting: localGreeting(),
    subtitle: null,
    project_highlight: null,
    urgent_todos: [],
    starters,
  };
}
