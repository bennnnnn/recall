import { useCallback } from "react";

import type { Learning } from "@/lib/api";
import { findLanguageProject } from "@/lib/projects/languageProject";

type Params = {
  projects: Learning[];
  draftProjectIdRef: React.MutableRefObject<string | null>;
};

export function useChatQuizContext({ projects, draftProjectIdRef }: Params) {
  const resolveQuizProjectId = useCallback((): string | null => {
    const fromDraft = draftProjectIdRef.current;
    if (fromDraft) return fromDraft;
    return findLanguageProject(projects)?.id ?? null;
  }, [projects, draftProjectIdRef]);

  return { resolveQuizProjectId };
}
