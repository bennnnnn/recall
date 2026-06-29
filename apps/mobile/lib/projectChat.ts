import type { ProjectDetail } from "@/lib/api";
import { isLanguageProject, levelLabel } from "@/lib/languageLevels";

function progressLine(project: ProjectDetail): string {
  const { stats } = project;
  if (stats.total === 0) return "I have no words yet — help me add some first.";
  return (
    `${stats.mastered_count} mastered, ${stats.new_count} new, ` +
    `${stats.learning_count} learning, ${stats.due_for_review} due for review.`
  );
}

/** General project chat opener. */
export function buildProjectAskPrompt(project: ProjectDetail): string {
  const goal = project.description?.trim()
    ? ` Goal: ${project.description.trim()}.`
    : "";

  if (isLanguageProject(project.kind)) {
    const lvl = levelLabel(project.level);
    return (
      `Help me with my "${project.title}" English project (${lvl}).${goal} ` +
      `${progressLine(project)} Add words, or suggest what to study next.`
    );
  }

  return (
    `Help me with my "${project.title}" project (${project.kind}).${goal} ` +
    `${progressLine(project)} What should I focus on next?`
  );
}

/** Starts an interactive multiple-choice vocabulary quiz in chat. */
export function buildProjectQuizPrompt(project: ProjectDetail): string {
  const lvl = levelLabel(project.level);
  const goal = project.description?.trim() ? ` ${project.description.trim()}.` : "";

  return (
    `Start an interactive vocabulary quiz for my "${project.title}" English project.\n` +
    `My English level: ${lvl}.${goal}\n` +
    `${progressLine(project)}\n\n` +
    "Quiz me in chat: one word at a time from my new and learning words, matched to my level.\n" +
    "Use this EXACT format for every question (required for the quiz card UI):\n\n" +
    "**Word:** apple [noun]\n" +
    "A) a red fruit\n" +
    "B) a vehicle\n" +
    "C) a feeling\n" +
    "D) a color\n\n" +
    "Do not wrap the word in extra asterisks. Wait for my answer before you explain. " +
    "If I'm right, congratulate me, give an example, and mark the word mastered automatically. " +
    "If wrong, explain and encourage me. Then ask if I want another question. " +
    "Begin with the first question now."
  );
}
