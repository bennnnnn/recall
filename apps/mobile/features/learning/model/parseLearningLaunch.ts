export type LearningLaunchAction = "start" | "continue";

export type ParsedLearningLaunch = {
  projectId: string;
  action: LearningLaunchAction;
};

const LEARNING_LAUNCH_FENCE_RE = /```learning_launch\s*\n([\s\S]*?)```/i;
const LEARNING_LAUNCH_FENCE_PARTIAL_RE = /```learning_launch[\s\S]*$/i;
const PROJECT_ID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function parseAction(value: unknown): LearningLaunchAction {
  return value === "start" ? "start" : "continue";
}

export function parseLearningLaunch(content: string): ParsedLearningLaunch | null {
  const match = content.match(LEARNING_LAUNCH_FENCE_RE);
  if (!match?.[1]) return null;
  try {
    const raw = JSON.parse(match[1].trim()) as Record<string, unknown>;
    const projectId = String(raw.project_id ?? "").trim();
    if (!PROJECT_ID_RE.test(projectId)) return null;
    return { projectId, action: parseAction(raw.action) };
  } catch {
    return null;
  }
}

export function hasLearningLaunchFence(content: string): boolean {
  return LEARNING_LAUNCH_FENCE_RE.test(content) || LEARNING_LAUNCH_FENCE_PARTIAL_RE.test(content);
}

export function stripLearningLaunchBlock(content: string): string {
  return content
    .replace(LEARNING_LAUNCH_FENCE_RE, "")
    .replace(LEARNING_LAUNCH_FENCE_PARTIAL_RE, "")
    .trim();
}
