import { useCallback, useState } from "react";

import type { Project } from "@/lib/api";
import { findLanguageProject } from "@/lib/languageProject";
import { findTriviaProject } from "@/lib/triviaProject";
import { quizVariantForProjectKind, type QuizVariant } from "@/lib/quizVariant";

type Params = {
  projects: Project[];
  draftProjectIdRef: React.MutableRefObject<string | null>;
};

export function useChatQuizContext({ projects, draftProjectIdRef }: Params) {
  const [quizLanguage, setQuizLanguage] = useState("en");
  const [quizVariant, setQuizVariant] = useState<QuizVariant>("vocab");

  const resolveQuizVariant = useCallback(
    (projectId: string | null | undefined): QuizVariant => {
      if (!projectId) return "vocab";
      const project = projects.find((item) => item.id === projectId);
      return quizVariantForProjectKind(project?.kind);
    },
    [projects],
  );

  const resolveQuizProjectId = useCallback((): string | null => {
    const fromDraft = draftProjectIdRef.current;
    if (fromDraft) return fromDraft;
    if (quizVariant === "trivia") {
      return findTriviaProject(projects)?.id ?? null;
    }
    if (quizVariant === "vocab") {
      return findLanguageProject(projects, "en")?.id ?? null;
    }
    return null;
  }, [projects, quizVariant, draftProjectIdRef]);

  return {
    quizLanguage,
    setQuizLanguage,
    quizVariant,
    setQuizVariant,
    resolveQuizVariant,
    resolveQuizProjectId,
  };
}
