import type { HomeProjectHighlight, LanguageLevel, Project, ProjectDetail, ProjectStats } from "@/lib/api";
import { resolveDailyGoal } from "@/lib/projects/dailyGoals";
import { isLanguageProject, levelLabel } from "@/lib/languageLevels";
import { languageLabel } from "@/lib/i18n/languages";
import { learningProjectTitle } from "@/lib/projects/projectUi";
import { VOCAB_QUIZ_FORMAT_BLOCK } from "@/lib/vocabQuizFormat";

const LESSON_FENCE_ONLY =
  "Reply with ONLY one ```vocab_quiz or ```vocab_card fence. " +
  "No vocab lists, check-ins, headings, or markdown essays.";

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
  if (!isLanguageProject(project.kind)) return false;
  return completedTodayCount(project.stats) >= resolveProjectDailyGoal(project);
}

export function remainingDailyGoal(project: ProjectDetail): number {
  return Math.max(0, resolveProjectDailyGoal(project) - completedTodayCount(project.stats));
}

export type ProjectAskPromptOptions = {
  /** Product screen title, e.g. "Words" or "General Knowledge". */
  screenTitle?: string;
  topicLabels?: string;
  difficultyLabel?: string;
};

function defaultScreenTitle(project: ProjectDetail): string {
  if (isLanguageProject(project.kind)) return languageLabel(project.target_language);
  return project.title;
}

function todayProgressClause(project: ProjectDetail): string {
  const daily = resolveProjectDailyGoal(project);
  const done = completedTodayCount(project.stats);
  const correct = project.stats.mastered_today;
    const missed = project.stats.missed_today ?? 0;
  if (isLanguageProject(project.kind)) {
    return `Today: ${done}/${daily} done (${correct} mastered, ${missed} failed)`;
  }
  return `Today: ${done}/${daily}`;
}

/** List/detail Continue — passes localized screen title, topics, and difficulty. */
export function buildProjectAskPromptFromProject(
  project: Project,
  t: (key: string) => string,
): string {
  const detail = projectDetailForChat(project);
  return buildProjectAskPrompt(detail, {
    screenTitle: learningProjectTitle(project.kind, t, project.title, project.target_language),
  });
}

function progressLine(project: ProjectDetail): string {
  const { stats, kind } = project;
  if (stats.total === 0) {
    if (isLanguageProject(kind)) return "I have no words yet — help me add some first.";
    return "I have nothing tracked yet — help me add some first.";
  }
  if (isLanguageProject(kind)) {
    return (
      `${stats.mastered_count} mastered, ${stats.new_count} new words, ` +
      `${stats.learning_count} learning, ${stats.due_for_review} due for review.`
    );
  }
  return (
    `${stats.mastered_count} mastered, ${stats.new_count} new, ` +
    `${stats.learning_count} in progress, ${stats.due_for_review} due for review.`
  );
}

/** Opens chat after a new vocabulary project is created. */
export function buildLanguageOnboardingPrompt(
  title: string,
  level: LanguageLevel,
  dailyGoal: number,
  targetLanguage = "en",
): string {
  const lvl = levelLabel(level);
  const name = languageLabel(targetLanguage);
  return (
    `I just set up my "${title}" ${name} vocabulary project.\n` +
    `My level: ${lvl}. My daily goal: ${dailyGoal} new words per session.\n\n` +
    `You're my ${name} tutor. Generate exactly ${dailyGoal} new vocabulary words matched to ${lvl} ` +
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
  const unit = "words";
  return (
    `Start a spaced-repetition review for my "${project.title}" project. ` +
    `I have ${due} ${unit} due for review. ` +
    `Quiz ONLY due items — do not add new ${unit} until the review queue is cleared. ` +
    `One question at a time in chat.`
  );
}

/** Home highlight card → in-chat daily session. */
export function buildHomeDailyQuizChatPrompt(highlight: HomeProjectHighlight): string {
  const { title, kind, cue } = highlight;
  if (cue === "start") {
    return (
      `Start today's "${title}" vocabulary session. ` +
      "One word at a time — mix teach→use (definition only, then I write a sentence — no example first), " +
      "use→define (show a sentence, ask what it means), and occasional A–D multiple choice. Begin now."
    );
  }
  return (
    `Continue my "${title}" vocabulary session. ` +
    "Next word: use a learning format (teach→use, use→define, or occasional MCQ) — vary it."
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
      `Level: ${lvl}. ${todayProgressClause(project)} — continue with the next word using a ` +
      `learning format (teach→use, use→define, or occasional MCQ). ${LESSON_FENCE_ONLY}`
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

/** Lesson window opener scoped to one learning-path chapter. */
export function buildChapterLessonPrompt(
  project: ProjectDetail,
  chapterTitle: string,
): string {
  const chapter = chapterTitle.trim();
  const name = languageLabel(project.target_language);
  const lvl = levelLabel(project.level);
  return (
    `Continue my ${name} lesson in the "${chapter}" chapter.\n` +
    `Level: ${lvl}. ${todayProgressClause(project)}\n` +
    `Teach and quiz only this chapter. Add any new words to "${chapter}". ` +
    `Use teach→use, use→define, or occasional MCQ — one word at a time. ${LESSON_FENCE_ONLY}`
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

/** Chat tutor mode — conversational teaching (vocab_card / mixed formats). */
export function buildProjectChatTutorPrompt(project: ProjectDetail): string {
  if (isLanguageProject(project.kind)) {
    return (
      `We're in **chat tutor mode** — teach one word at a time with definition only on the card ` +
      `(no example sentence until after I try). Use the vocab_card format. ` +
      `No multiple choice unless I ask to be quizzed.\n\n` +
      buildProjectAskPrompt(project)
    );
  }
  return buildProjectAskPrompt(project);
}

/** Starts an interactive multiple-choice vocabulary quiz in chat. */
export function buildProjectQuizPrompt(project: ProjectDetail): string {
  const lvl = levelLabel(project.level);
  const name = languageLabel(project.target_language);
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
    `Start an interactive vocabulary session for my "${project.title}" ${name} project.\n` +
    `My ${name} level: ${lvl}.${goal}\n` +
    `${progressLine(project)}\n\n` +
    "One word at a time from my new and learning words, matched to my level.\n" +
    "Mix learning formats: teach→use (```vocab_card``` with word+definition only — " +
    "no example_sentence — then ask for a sentence), " +
    "use→define (example sentence then open definition), and occasional A–D ```vocab_quiz```.\n\n" +
    "When you use MCQ, use this format:\n\n" +
    `${VOCAB_QUIZ_FORMAT_BLOCK}\n\n` +
    "Wait for my answer before you explain. " +
    "If I'm right, congratulate me and mark the word mastered. " +
    "If wrong, hint and let me try again. " +
    "Begin with the first word now — prefer teach→use or use→define over MCQ."
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
