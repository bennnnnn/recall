import type { LanguageLevel, ProjectDetail } from "@/lib/api";
import { isLanguageProject, levelLabel } from "@/lib/languageLevels";
import { programmingLanguageLabel, type ProgrammingLanguageId } from "@/lib/programmingLanguages";
import { VOCAB_QUIZ_FORMAT_BLOCK } from "@/lib/vocabQuizFormat";

function progressLine(project: ProjectDetail): string {
  const { stats, kind } = project;
  if (stats.total === 0) {
    if (kind === "math") return "I have no topics yet — help me add some first.";
    if (isLanguageProject(kind)) return "I have no words yet — help me add some first.";
    return "I have nothing tracked yet — help me add some first.";
  }
  if (isLanguageProject(kind)) {
    return (
      `${stats.mastered_count} mastered, ${stats.new_count} new words, ` +
      `${stats.learning_count} learning, ${stats.due_for_review} due for review.`
    );
  }
  if (kind === "math") {
    return (
      `${stats.mastered_count} concepts mastered, ${stats.new_count} new topics, ` +
      `${stats.learning_count} in progress, ${stats.due_for_review} to review.`
    );
  }
  if (kind === "trivia") {
    return (
      `${stats.mastered_count} facts learned, ${stats.mastered_today} correct today, ` +
      `${stats.total} total questions saved.`
    );
  }
  return (
    `${stats.mastered_count} mastered, ${stats.new_count} new, ` +
    `${stats.learning_count} in progress, ${stats.due_for_review} due for review.`
  );
}

/** Opens chat after a new English vocabulary project is created. */
export function buildEnglishOnboardingPrompt(
  title: string,
  level: LanguageLevel,
  dailyGoal: number,
): string {
  const lvl = levelLabel(level);
  return (
    `I just set up my "${title}" English vocabulary project.\n` +
    `My level: ${lvl}. My daily goal: ${dailyGoal} new words per session.\n\n` +
    `You're my English tutor. Generate exactly ${dailyGoal} new vocabulary words matched to ${lvl} ` +
    `(high-frequency words I'll actually use). Save them to this project with part_of_speech, ` +
    `definition, and example_sentence.\n\n` +
    `Then teach each word briefly and quiz me one at a time until I master all ${dailyGoal}. ` +
    `When I'm done, I'll come back tomorrow for the next batch.\n\n` +
    `Check in: does this level feel too easy, too hard, or about right?`
  );
}

/** Opens chat after a new programming project is created — starts chapter 1. */
export function buildProgrammingOnboardingPrompt(
  language: ProgrammingLanguageId,
  firstChapter: string,
  firstTopics: string[],
): string {
  const stack = programmingLanguageLabel(language);
  const topics = firstTopics.join(", ");
  return (
    `I just started learning ${stack} programming.\n\n` +
    `Begin with chapter 1: **${firstChapter}**. Cover these sub-topics in order: ${topics}. ` +
    `Teach clearly with ${stack} examples. Mark each sub-topic mastered when I demonstrate it, ` +
    `then move to the next sub-topic and chapter.\n\n` +
    `Follow the fixed curriculum — do not skip ahead unless I ask.`
  );
}

/** Opens chat after a new general-knowledge trivia project is created. */
export function buildTriviaOnboardingPrompt(topicLabels: string, dailyGoal: number): string {
  return (
    `I just set up my daily general knowledge quiz.\n` +
    `Topics: ${topicLabels}. Daily goal: ${dailyGoal} correct answers per session.\n\n` +
    `Run a multiple-choice quiz in chat — one question at a time from my topics. ` +
    `Use vocab_quiz JSON with quiz_type=trivia: word=topic label (History, Science, …), ` +
    `question=the full question. Never use part_of_speech. ` +
    `When I answer correctly, save the fact and mark it mastered.\n\n` +
    `Mix topics and keep questions interesting but fair. Start question 1 now.`
  );
}

/** General project chat opener. */
export function buildProjectAskPrompt(project: ProjectDetail): string {
  const goal = project.description?.trim()
    ? ` Goal: ${project.description.trim()}.`
    : "";

  if (isLanguageProject(project.kind)) {
    const lvl = levelLabel(project.level);
    const daily = project.daily_goal ?? 10;
    const today =
      project.stats.mastered_today > 0 || project.stats.pending_today > 0
        ? ` Today: ${project.stats.mastered_today}/${daily} mastered`
        : "";
    return (
      `Help me with my "${project.title}" English project (${lvl}, ${daily} words/day).${goal}` +
      `${progressLine(project)}.${today} ` +
      `If I have no pending words, generate today's batch. Otherwise quiz what I'm still learning.`
    );
  }

  if (project.kind === "trivia") {
    const daily = project.daily_goal ?? 10;
    const remaining = Math.max(0, daily - project.stats.mastered_today);
    return (
      `Continue my daily general knowledge quiz (${daily} correct/day).${goal} ` +
      `${progressLine(project)} ` +
      (remaining > 0
        ? `I need ${remaining} more correct answers today — ask the next question.`
        : `I hit today's goal — offer a bonus question or wrap up.`)
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
    `${VOCAB_QUIZ_FORMAT_BLOCK}\n\n` +
    "Do not wrap the word in extra asterisks. Wait for my answer before you explain. " +
    "If I'm right, congratulate me, give an example, and mark the word mastered automatically. " +
    "If wrong, explain and encourage me. Then ask if I want another question. " +
    "Begin with the first question now."
  );
}

/** Practice-problem opener for math / general (non-language, non-programming) projects. */
export function buildProjectPracticePrompt(project: ProjectDetail): string {
  const goal = project.description?.trim() ? ` Goal: ${project.description.trim()}.` : "";
  return (
    `Give me a practice problem for my "${project.title}" project (${project.kind}).${goal} ` +
    `Start at my current level, walk through one problem step by step, and check my answer. ` +
    `Then suggest what to try next.`
  );
}
