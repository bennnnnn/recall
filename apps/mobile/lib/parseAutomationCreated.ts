import { AUTOMATION_FREQUENCIES, type AutomationFrequency } from "@/lib/api/types";

/** Server-attached confirmation after a chat-based ```automation create fence
 * (see apps/api/app/services/automations/fences.py). Renders as a small
 * tappable chip — "Every day · Find L3 backend jobs" — that opens the My Job
 * detail screen, mirroring ChatGPT's "Mondays · Learn Spanish" task chip.
 */
export type ParsedAutomationCreated = {
  id: string;
  prompt: string;
  frequency: AutomationFrequency;
  nextRunAt: string;
};

const AUTOMATION_CREATED_FENCE_RE = /```automation_created\s*\n([\s\S]*?)```/i;
const AUTOMATION_CREATED_FENCE_PARTIAL_RE = /```automation_created[\s\S]*$/i;

function isAutomationFrequency(value: string): value is AutomationFrequency {
  return (AUTOMATION_FREQUENCIES as readonly string[]).includes(value);
}

export function parseAutomationCreated(content: string): ParsedAutomationCreated | null {
  const match = content.match(AUTOMATION_CREATED_FENCE_RE);
  if (!match?.[1]) return null;
  try {
    const raw = JSON.parse(match[1].trim()) as Record<string, unknown>;
    const id = String(raw.id ?? "").trim();
    const prompt = String(raw.prompt ?? "").trim();
    const frequency = String(raw.frequency ?? "").trim();
    const nextRunAt = String(raw.next_run_at ?? "").trim();
    if (!id || !prompt || !frequency || !nextRunAt || !isAutomationFrequency(frequency)) {
      return null;
    }
    return { id, prompt, frequency, nextRunAt };
  } catch {
    return null;
  }
}

export function hasAutomationCreatedFence(content: string): boolean {
  return (
    AUTOMATION_CREATED_FENCE_RE.test(content) || AUTOMATION_CREATED_FENCE_PARTIAL_RE.test(content)
  );
}

export function stripAutomationCreatedBlock(content: string): string {
  return content
    .replace(AUTOMATION_CREATED_FENCE_RE, "")
    .replace(AUTOMATION_CREATED_FENCE_PARTIAL_RE, "")
    .trim();
}
