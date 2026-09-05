import type { ProjectDetail, ProjectItem } from "@/lib/api";
import { chapterKey } from "@/lib/projects/chapterAccess";

export type VocabularyGroup = {
  key: string;
  title: string;
  domain?: string;
  items: ProjectItem[];
};

function searchKey(value: string): string {
  return value.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().trim();
}

/** Browse only the vocabulary groups returned by the current project response. */
export function vocabularyGroups(project: ProjectDetail, query: string): VocabularyGroup[] {
  const term = searchKey(query);
  const domains = new Map(
    (project.path_progress ?? []).map((chapter) => [chapterKey(chapter.title), chapter.domain]),
  );
  return project.lists.flatMap((group, index) => {
    const items = group.items.filter((item) => {
      if (!item.content.trim()) return false;
      if (!term) return true;
      return [item.content, item.definition, item.simple_gloss].some(
        (value) => value != null && searchKey(value).includes(term),
      );
    });
    return items.length
      ? [
          {
            key: `${index}:${group.list_title}`,
            title: group.list_title,
            domain: domains.get(chapterKey(group.list_title)) ?? undefined,
            items,
          },
        ]
      : [];
  });
}

export function vocabularyPath(projectId: string): `/projects/${string}/vocabulary` {
  return `/projects/${projectId}/vocabulary`;
}
