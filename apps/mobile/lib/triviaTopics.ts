/** General-knowledge quiz subjects — ids stored comma-separated in project.description. */
export const TRIVIA_TOPICS = [
  { id: "history", labelKey: "projects.trivia.topic.history" },
  { id: "science", labelKey: "projects.trivia.topic.science" },
  { id: "geography", labelKey: "projects.trivia.topic.geography" },
  { id: "arts", labelKey: "projects.trivia.topic.arts" },
  { id: "technology", labelKey: "projects.trivia.topic.technology" },
  { id: "nature", labelKey: "projects.trivia.topic.nature" },
] as const;

export type TriviaTopicId = (typeof TRIVIA_TOPICS)[number]["id"];

export function encodeTriviaTopics(topicIds: string[]): string {
  return topicIds.map((id) => id.trim().toLowerCase()).filter(Boolean).join(",");
}

export function parseTriviaTopics(description: string | null | undefined): string[] {
  if (!description?.trim()) return [];
  return description
    .split(",")
    .map((part) => part.trim().toLowerCase())
    .filter(Boolean);
}

export function triviaTopicLabel(
  id: string,
  t: (key: string) => string,
): string {
  const match = TRIVIA_TOPICS.find((topic) => topic.id === id);
  return match ? t(match.labelKey) : id;
}

export function formatTriviaTopicLabels(
  topicIds: string[],
  t: (key: string) => string,
): string {
  return topicIds.map((id) => triviaTopicLabel(id, t)).join(", ");
}
