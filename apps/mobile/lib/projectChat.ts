import type { LanguageLevel, ProjectDetail } from "@/lib/api";
import { resolveDailyGoal } from "@/lib/dailyGoals";
import { isLanguageProject, levelLabel } from "@/lib/languageLevels";
import { VOCAB_QUIZ_FORMAT_BLOCK } from "@/lib/vocabQuizFormat";

export function resolveProjectDailyGoal(project: ProjectDetail): number {
  return resolveDailyGoal(project.daily_goal);
}

export function isDailyGoalMet(project: ProjectDetail): boolean {
  if (!isLanguageProject(project.kind) && project.kind !== "trivia") return false;
  return project.stats.mastered_today >= resolveProjectDailyGoal(project);
}

export function remainingDailyGoal(project: ProjectDetail): number {
  return Math.max(0, resolveProjectDailyGoal(project) - project.stats.mastered_today);
}

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
    const daily = resolveProjectDailyGoal(project);
    const done = project.stats.mastered_today;
    if (isDailyGoalMet(project)) {
      return (
        `I finished my daily goal of ${daily} words on my "${project.title}" English project (${lvl}).${goal}\n` +
        `${progressLine(project)}\n\n` +
        "Tell me clearly that today's goal is complete — congratulate me. " +
        "Do NOT add or sync new words unless I explicitly ask for a bonus batch beyond today's goal. " +
        "Offer to quiz words I already know for review, or invite me back tomorrow."
      );
    }
    const remaining = remainingDailyGoal(project);
    const today = ` Today: ${done}/${daily} mastered — ${remaining} left for today's goal.`;
    return (
      `Help me with my "${project.title}" English project (${lvl}, ${daily} words/day).${goal}` +
      `${progressLine(project)}.${today} ` +
      "Quiz my new and learning words first. Only add fresh words if I still need them to reach today's goal — " +
      "never exceed today's goal without my explicit ok."
    );
  }

  if (project.kind === "trivia") {
    const daily = resolveProjectDailyGoal(project);
    const remaining = remainingDailyGoal(project);
    if (isDailyGoalMet(project)) {
      return (
        `I finished my daily goal of ${daily} correct answers on my general knowledge quiz.${goal} ` +
        `${progressLine(project)}\n\n` +
        "Tell me clearly that today's quiz goal is complete. Do NOT ask new quiz questions unless I " +
        "explicitly want bonus questions beyond today's goal."
      );
    }
    return (
      `Continue my daily general knowledge quiz (${daily} correct/day).${goal} ` +
      `${progressLine(project)} ` +
      `I need ${remaining} more correct answers today — ask the next question.`
    );
  }

  return (
    `Help me with my "${project.title}" project (${project.kind}).${goal} ` +
    `${progressLine(project)} What should I focus on next?`
  );
}

/** Explicit opt-in when the user wants questions beyond today's daily goal. */
export function buildProjectBonusQuestionsPrompt(project: ProjectDetail): string {
  const daily = resolveProjectDailyGoal(project);
  return (
    `I already finished my daily goal of ${daily} correct answers on my general knowledge quiz today ` +
    `(${project.stats.mastered_today}/${daily}).\n\n` +
    "I want BONUS trivia questions beyond today's goal. Confirm I'm ok with extra questions, then ask " +
    "multiple-choice questions one at a time using vocab_quiz JSON. Do not start until I confirm."
  );
}

/** Explicit opt-in when the user wants words beyond today's daily goal. */
export function buildProjectBonusWordsPrompt(project: ProjectDetail): string {
  const daily = resolveProjectDailyGoal(project);
  const lvl = levelLabel(project.level);
  return (
    `I already finished my daily goal of ${daily} words on "${project.title}" today ` +
    `(${project.stats.mastered_today}/${daily} mastered). My level: ${lvl}.\n\n` +
    `I want a BONUS batch beyond today's goal. Confirm I'm ok with extra words, then add up to ${daily} ` +
    "fresh words at my level — teach and quiz them one at a time. Do not start until I confirm."
  );
}

/** Chat tutor mode — conversational teaching (language: vocab_card; trivia: facts only). */
export function buildProjectChatTutorPrompt(project: ProjectDetail): string {
  if (project.kind === "trivia") {
    return (
      `We're in **chat tutor mode** for my general knowledge quiz — share facts and explain topics in plain prose. ` +
      `Do NOT teach English vocabulary, do NOT use vocab_card blocks, and do NOT use multiple choice unless I ask.\n\n` +
      buildProjectAskPrompt(project)
    );
  }
  if (isLanguageProject(project.kind)) {
    return (
      `We're in **chat tutor mode** — teach one word at a time with definition and example. ` +
      `Use the vocab_card format for each word. No multiple choice unless I ask to be quizzed.\n\n` +
      buildProjectAskPrompt(project)
    );
  }
  return buildProjectAskPrompt(project);
}

/** Exam quiz mode — multiple-choice cards only. */
export function buildProjectExamPrompt(project: ProjectDetail): string {
  if (isLanguageProject(project.kind)) {
    return buildProjectQuizPrompt(project);
  }
  if (project.kind === "trivia") {
    const base = buildProjectAskPrompt(project);
    return (
      `We're in **exam quiz mode** — one multiple-choice trivia question per turn using vocab_quiz JSON. ` +
      `Wait for A–D before explaining.\n\n${base}`
    );
  }
  return buildProjectAskPrompt(project);
}

/** Starts an interactive multiple-choice vocabulary quiz in chat. */
export function buildProjectQuizPrompt(project: ProjectDetail): string {
  const lvl = levelLabel(project.level);
  const goal = project.description?.trim() ? ` ${project.description.trim()}.` : "";
  const daily = resolveProjectDailyGoal(project);

  if (isDailyGoalMet(project)) {
    return (
      `I finished my daily goal of ${daily} words on "${project.title}" today.\n` +
      `${progressLine(project)}\n\n` +
      "Tell me today's goal is done. Ask whether I want a bonus batch or just review words I already know. " +
      "Do not add new words unless I explicitly ask for more beyond today's goal."
    );
  }

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

/** Practice-problem opener for math / general projects. */
export function buildProjectPracticePrompt(project: ProjectDetail): string {
  const goal = project.description?.trim() ? ` Goal: ${project.description.trim()}.` : "";
  return (
    `Give me a practice problem for my "${project.title}" project (${project.kind}).${goal} ` +
    `Start at my current level, walk through one problem step by step, and check my answer. ` +
    `Then suggest what to try next.`
  );
}
