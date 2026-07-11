import type { HomeProjectHighlight, LanguageLevel, Project, ProjectDetail, ProjectStats } from "@/lib/api";
import { resolveDailyGoal } from "@/lib/dailyGoals";
import { isLanguageProject, levelLabel } from "@/lib/languageLevels";
import { learningProjectTitle } from "@/lib/projectUi";
import {
  formatTriviaTopicLabels,
  parseTriviaTopics,
  triviaDifficultyLabel,
} from "@/lib/triviaTopics";
import { VOCAB_QUIZ_FORMAT_BLOCK, TRIVIA_QUIZ_FORMAT_BLOCK } from "@/lib/vocabQuizFormat";

const EMPTY_STATS: ProjectStats = {
  total: 0,
  new_count: 0,
  learning_count: 0,
  mastered_count: 0,
  added_this_week: 0,
  due_for_review: 0,
  mastered_today: 0,
  missed_today: 0,
  pending_today: 0,
};

/** Minimal detail shape for chat prompts when only list `Project` + stats are available. */
export function projectDetailForChat(project: Project): ProjectDetail {
  const stats = project.stats ?? EMPTY_STATS;
  return {
    ...project,
    mastered_count: stats.mastered_count,
    total_count: stats.total,
    stats,
    daily_history: [],
    daily_items_by_date: {},
    lists: [],
  };
}

export function resolveProjectDailyGoal(project: ProjectDetail): number {
  return resolveDailyGoal(project.daily_goal);
}

/** Correct + still-missed questions finished toward today's goal. */
export function completedTodayCount(stats: Pick<ProjectStats, "mastered_today" | "missed_today">): number {
  return Math.max(0, (stats.mastered_today ?? 0) + (stats.missed_today ?? 0));
}

export function isDailyGoalMet(project: ProjectDetail): boolean {
  if (!isLanguageProject(project.kind) && project.kind !== "trivia") return false;
  return completedTodayCount(project.stats) >= resolveProjectDailyGoal(project);
}

export function remainingDailyGoal(project: ProjectDetail): number {
  return Math.max(0, resolveProjectDailyGoal(project) - completedTodayCount(project.stats));
}

export type ProjectAskPromptOptions = {
  /** Product screen title, e.g. "Words" or "General Knowledge". */
  screenTitle?: string;
  /** Human-readable trivia topics, e.g. "History, Science". */
  topicLabels?: string;
  /** Trivia difficulty label from settings. */
  difficultyLabel?: string;
};

function defaultScreenTitle(project: ProjectDetail): string {
  if (project.kind === "trivia") return "General Knowledge";
  if (isLanguageProject(project.kind)) return "Words";
  return project.title;
}

function formatTriviaTopicIdsFallback(description: string | null | undefined): string {
  const ids = parseTriviaTopics(description);
  if (ids.length === 0) return "";
  return ids.map((id) => id.charAt(0).toUpperCase() + id.slice(1)).join(", ");
}

function triviaTopicsClause(project: ProjectDetail, topicLabels?: string): string {
  const labels = topicLabels?.trim() || formatTriviaTopicIdsFallback(project.description);
  return labels ? `Topics: ${labels}. ` : "";
}

function todayProgressClause(project: ProjectDetail): string {
  const daily = resolveProjectDailyGoal(project);
  const done = completedTodayCount(project.stats);
  const correct = project.stats.mastered_today;
  const missed = project.stats.missed_today ?? 0;
  if (project.kind === "trivia") {
    return `Today: ${done}/${daily} done (${correct} correct, ${missed} missed)`;
  }
  if (isLanguageProject(project.kind)) {
    return `Today: ${done}/${daily} done (${correct} mastered, ${missed} missed)`;
  }
  return `Today: ${done}/${daily}`;
}

/** List/detail Continue — passes localized screen title, topics, and difficulty. */
export function buildProjectAskPromptFromProject(
  project: Project,
  t: (key: string) => string,
): string {
  const detail = projectDetailForChat(project);
  const isTrivia = project.kind === "trivia";
  return buildProjectAskPrompt(detail, {
    screenTitle: learningProjectTitle(project.kind, t, project.title),
    topicLabels: isTrivia
      ? formatTriviaTopicLabels(parseTriviaTopics(project.description), t)
      : undefined,
    difficultyLabel: isTrivia ? triviaDifficultyLabel(project.level, t) : undefined,
  });
}

function progressLine(project: ProjectDetail): string {
  const { stats, kind } = project;
  if (stats.total === 0) {
    if (isLanguageProject(kind)) return "I have no words yet — help me add some first.";
    if (kind === "trivia") return "I have no facts yet — help me add some first.";
    return "I have nothing tracked yet — help me add some first.";
  }
  if (isLanguageProject(kind)) {
    return (
      `${stats.mastered_count} mastered, ${stats.new_count} new words, ` +
      `${stats.learning_count} learning, ${stats.due_for_review} due for review.`
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
    `(high-frequency words I'll actually use). Save them to this project with ` +
    `definition and example_sentence.\n\n` +
    `Then teach each word briefly and quiz me one at a time until I master all ${dailyGoal}. ` +
    `When I'm done, I'll come back tomorrow for the next batch.\n\n` +
    `Check in: does this level feel too easy, too hard, or about right?`
  );
}

/** Opens chat for spaced-repetition review of due items only. */
export function buildProjectReviewPrompt(project: ProjectDetail): string {
  const due = project.stats.due_for_review;
  const unit = project.kind === "trivia" ? "facts" : "words";
  return (
    `Start a spaced-repetition review for my "${project.title}" project. ` +
    `I have ${due} ${unit} due for review. ` +
    `Quiz ONLY due items — do not add new ${unit} until the review queue is cleared. ` +
    `One question at a time in chat.`
  );
}

/** Opens chat after a new general-knowledge trivia project is created. */
export function buildTriviaOnboardingPrompt(
  topicLabels: string,
  dailyGoal: number,
  level: LanguageLevel,
): string {
  const lvl = levelLabel(level);
  return (
    `I just set up my daily general knowledge quiz.\n` +
    `Topics: ${topicLabels}. Difficulty: ${lvl}. Daily goal: ${dailyGoal} correct answers per session.\n\n` +
    `Run a multiple-choice quiz in chat — one question at a time from my topics at ${lvl} difficulty. ` +
    `Use vocab_quiz JSON with quiz_type=trivia: word=topic label (History, Science, …), ` +
    `question=the full question. ` +
    `When I answer correctly, save the fact and mark it mastered.\n\n` +
    `Mix topics and keep questions interesting but fair. Start question 1 now.`
  );
}

/** Home highlight card → in-chat daily session (LLM picks format each turn). */
export function buildHomeDailyQuizChatPrompt(highlight: HomeProjectHighlight): string {
  const { title, kind, cue } = highlight;
  if (kind === "trivia") {
    if (cue === "start") {
      return (
        `Start my daily "${title}" general-knowledge session. ` +
        "Quiz me in chat — one question at a time. You choose the format. Begin now."
      );
    }
    return (
      `Continue my daily "${title}" session. ` +
      "Ask the next question in chat — you pick the format."
    );
  }
  if (cue === "start") {
    return (
      `Start today's "${title}" vocabulary session. ` +
      "Teach and quiz in chat — one word at a time. You choose the format. Begin now."
    );
  }
  return (
    `Continue my "${title}" vocabulary session. ` +
    "Teach or quiz the next word in chat — you pick the format."
  );
}

/** General project chat opener. */
export function buildProjectAskPrompt(
  project: ProjectDetail,
  options: ProjectAskPromptOptions = {},
): string {
  const screenTitle = options.screenTitle?.trim() || defaultScreenTitle(project);

  if (isLanguageProject(project.kind)) {
    const lvl = levelLabel(project.level);
    const daily = resolveProjectDailyGoal(project);
    if (isDailyGoalMet(project)) {
      return (
        `I finished my daily goal of ${daily} words on my ${screenTitle} session (Level: ${lvl}).\n` +
        `${progressLine(project)}\n\n` +
        "Tell me clearly that today's goal is complete — congratulate me. " +
        "Do NOT add or sync new words unless I explicitly ask for a bonus batch beyond today's goal. " +
        "Offer to quiz words I already know for review, or invite me back tomorrow."
      );
    }
    return (
      `Continue my ${screenTitle} session.\n` +
      `Level: ${lvl}. ${todayProgressClause(project)} — ask the next multiple-choice question.`
    );
  }

  if (project.kind === "trivia") {
    const daily = resolveProjectDailyGoal(project);
    const topics = triviaTopicsClause(project, options.topicLabels);
    const difficulty = options.difficultyLabel
      ? `Difficulty: ${options.difficultyLabel}. `
      : "";
    if (isDailyGoalMet(project)) {
      return (
        `I finished my daily goal of ${daily} correct on my ${screenTitle} session. ` +
        `${topics}${difficulty}\n` +
        `${progressLine(project)}\n\n` +
        "Tell me clearly that today's quiz goal is complete. Do NOT ask new quiz questions unless I " +
        "explicitly want bonus questions beyond today's goal."
      );
    }
    return (
      `Continue my ${screenTitle} session.\n` +
      `${topics}${difficulty}${todayProgressClause(project)} — ask the next multiple-choice question.`
    );
  }

  const goal = project.description?.trim()
    ? `Goal: ${project.description.trim()}. `
    : "";
  return (
    `Help me with my "${project.title}" project (${project.kind}). ${goal}` +
    `${progressLine(project)} What should I focus on next?`
  );
}

/** Explicit opt-in when the user wants questions beyond today's daily goal. */
export function buildProjectBonusQuestionsPrompt(project: ProjectDetail): string {
  const daily = resolveProjectDailyGoal(project);
  return (
    `I already finished my daily goal of ${daily} correct answers on my general knowledge quiz today ` +
    `(${project.stats.mastered_today}/${daily}).\n\n` +
    "I want BONUS trivia questions beyond today's goal. Ask ONE multiple-choice question at a time " +
    "using vocab_quiz JSON with quiz_type=trivia. Do not use spoiler syntax or bullet lists.\n\n" +
    `${TRIVIA_QUIZ_FORMAT_BLOCK}\n\n` +
    "Start the first bonus question now."
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
