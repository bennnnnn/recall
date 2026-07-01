import type { Ionicons } from "@expo/vector-icons";

export const ENGLISH_LEARNING_TOPICS = [
  { id: "vocabulary", icon: "book-outline" },
  { id: "grammar", icon: "school-outline" },
  { id: "pronunciation", icon: "mic-outline" },
  { id: "reading", icon: "newspaper-outline" },
  { id: "writing", icon: "pencil-outline" },
  { id: "listening", icon: "headset-outline" },
  { id: "speaking", icon: "chatbubble-outline" },
] as const satisfies ReadonlyArray<{
  id: string;
  icon: keyof typeof Ionicons.glyphMap;
}>;

export type EnglishLearningTopicId = (typeof ENGLISH_LEARNING_TOPICS)[number]["id"];

export function englishTopicLabel(
  topicId: EnglishLearningTopicId,
  t: (key: string) => string,
): string {
  return t(`projects.english_topics.${topicId}`);
}

export function englishTopicsDescription(
  topics: EnglishLearningTopicId[],
  t: (key: string) => string,
): string {
  if (topics.length === 0) return "";
  const labels = topics.map((id) => englishTopicLabel(id, t)).join(", ");
  return `Focus areas: ${labels}`;
}

export function sortEnglishTopics(topics: EnglishLearningTopicId[]): EnglishLearningTopicId[] {
  const order = ENGLISH_LEARNING_TOPICS.map((item) => item.id);
  return [...topics].sort((a, b) => order.indexOf(a) - order.indexOf(b));
}
