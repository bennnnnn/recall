import type { Todo } from "@/lib/api";
import { DEFAULT_TOPIC, normalizeTopic } from "@/lib/todoTopics";

export type ListGroup = {
  topic: string;
  title: string;
  isDefault: boolean;
  open: Todo[];
  done: Todo[];
};

export function isDefaultListTopic(topic: string): boolean {
  return normalizeTopic(topic) === DEFAULT_TOPIC;
}

export function displayGroupTitle(topic: string, labelForDefault: string): string {
  return isDefaultListTopic(topic) ? labelForDefault : topic;
}

export function sortListItems(items: Todo[]): Todo[] {
  return [...items].sort((a, b) => {
    const aOrder = a.sort_order ?? Number.MAX_SAFE_INTEGER;
    const bOrder = b.sort_order ?? Number.MAX_SAFE_INTEGER;
    if (aOrder !== bOrder) return aOrder - bOrder;
    return a.created_at.localeCompare(b.created_at);
  });
}

export function buildListGroups(
  items: Todo[],
  groupOrder: string[],
  defaultGroupLabel: string,
): ListGroup[] {
  const listItems = items.filter((item) => !item.due_at);
  const byTopic = new Map<string, Todo[]>();

  for (const item of listItems) {
    const topic = normalizeTopic(item.topic);
    byTopic.set(topic, [...(byTopic.get(topic) ?? []), item]);
  }

  const allTopics = new Set([...byTopic.keys(), ...groupOrder]);
  const orderedTopics = [
    ...groupOrder.filter((topic) => allTopics.has(topic)),
    ...[...allTopics]
      .filter((topic) => !groupOrder.includes(topic))
      .sort((a, b) => a.localeCompare(b)),
  ];

  const seen = new Set<string>();
  const groups: ListGroup[] = [];
  for (const topic of orderedTopics) {
    if (seen.has(topic)) continue;
    seen.add(topic);
    const topicItems = byTopic.get(topic) ?? [];
    groups.push({
      topic,
      title: displayGroupTitle(topic, defaultGroupLabel),
      isDefault: isDefaultListTopic(topic),
      open: sortListItems(topicItems.filter((item) => !item.checked)),
      done: sortListItems(topicItems.filter((item) => item.checked)),
    });
  }
  return groups;
}

export function mergeGroupOrder(current: string[], topics: string[]): string[] {
  const next = [...current.filter((topic) => topics.includes(topic))];
  for (const topic of topics) {
    if (!next.includes(topic)) next.push(topic);
  }
  return next;
}

export function listGroupTopics(groups: ListGroup[]): string[] {
  return groups.map((group) => group.topic);
}
