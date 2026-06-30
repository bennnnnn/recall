import { api, type HomeScreen, type HomeStarter } from "@/lib/api";

function looksInternal(text: string): boolean {
  const clean = text.trim();
  if (!clean) return true;
  return /^(?:the\s+)?user(?:'s|\s+is|\s+has|\s+name\s+is|\s+prefers|\s+likes|\s+wants)\b/i.test(
    clean,
  );
}

function localGreeting(): string {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return "Good morning";
  if (hour >= 12 && hour < 17) return "Good afternoon";
  if (hour >= 17 && hour < 22) return "Good evening";
  return "Hey there";
}

function timeStarters(): HomeStarter[] {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) {
    return [
      {
        text: "Plan my day",
        prompt: "Help me plan my day based on what you know about me.",
        kind: "time",
      },
    ];
  }
  if (hour >= 12 && hour < 17) {
    return [
      {
        text: "How's your day?",
        prompt: "How's my day looking so far — anything you think I should prioritize?",
        kind: "time",
      },
    ];
  }
  if (hour >= 17 && hour < 22) {
    return [
      {
        text: "How did today go?",
        prompt: "How did my day go? Help me reflect and wrap up loose ends.",
        kind: "time",
      },
    ];
  }
  return [
    {
      text: "Quick thought",
      prompt: "I have a quick thought I want to talk through.",
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
      text: item.text.slice(0, 48),
      prompt,
      kind: "general",
    });
  }

  if (starters.length === 0) {
    starters.push({
      text: "Help me think",
      prompt: "I want to talk something through — ask me a good opening question.",
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
