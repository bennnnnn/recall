/** General-knowledge quiz subjects — ids stored comma-separated in project.description. */
import type { LanguageLevel } from "@/lib/api";

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

export const TRIVIA_DIFFICULTY_LEVELS: { level: LanguageLevel; labelKey: string }[] = [
  { level: "level1", labelKey: "projects.trivia.difficulty.easy" },
  { level: "level3", labelKey: "projects.trivia.difficulty.medium" },
  { level: "level5", labelKey: "projects.trivia.difficulty.hard" },
];

export function triviaDifficultyLabel(
  level: LanguageLevel,
  t: (key: string) => string,
): string {
  const match = TRIVIA_DIFFICULTY_LEVELS.find((item) => item.level === level);
  return match ? t(match.labelKey) : level;
}

export function triviaDifficultyPickerOptions(
  t: (key: string) => string,
): { key: LanguageLevel; label: string }[] {
  return TRIVIA_DIFFICULTY_LEVELS.map((item) => ({
    key: item.level,
    label: t(item.labelKey),
  }));
}
