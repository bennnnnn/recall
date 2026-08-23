/** Shared quiz card format — keep in sync with apps/api/app/services/projects.py */

export const VOCAB_QUIZ_MARKDOWN_EXAMPLE = [
  "**Word:** see you later",
  "Which word completes this sentence?",
  "_____ — I have a meeting now.",
  "A) see you later",
  "B) water",
  "C) yesterday",
  "D) expensive",
].join("\n");

export const VOCAB_QUIZ_FENCE_EXAMPLE = [
  "```vocab_quiz",
  JSON.stringify({
    word: "see you later",
    question: "Which word completes this sentence? _____ — I have a meeting now.",
    correct: "A",
    choices: [
      { letter: "A", text: "see you later" },
      { letter: "B", text: "water" },
      { letter: "C", text: "yesterday" },
      { letter: "D", text: "expensive" },
    ],
  }),
  "```",
].join("\n");

export const TRIVIA_QUIZ_FENCE_EXAMPLE = [
  "```vocab_quiz",
  JSON.stringify({
    quiz_type: "trivia",
    word: "History",
    question: "Which ancient wonder was a giant statue at the harbor of Rhodes?",
    correct: "A",
    choices: [
      { letter: "A", text: "Colossus of Rhodes" },
      { letter: "B", text: "Great Pyramid of Giza" },
      { letter: "C", text: "Hanging Gardens of Babylon" },
      { letter: "D", text: "Lighthouse of Alexandria" },
    ],
  }),
  "```",
].join("\n");

export const TRIVIA_QUIZ_FORMAT_BLOCK = [
  "Use this EXACT format for each question (include the markdown A–D list AND the fence):",
  TRIVIA_QUIZ_FENCE_EXAMPLE,
  "One question per message. word = topic label (History, Science, …). No spoiler syntax.",
].join("\n\n");

export const VOCAB_QUIZ_FORMAT_BLOCK = `${VOCAB_QUIZ_MARKDOWN_EXAMPLE}\n\nThen append this machine-readable block (required — include correct letter A–D):\n${VOCAB_QUIZ_FENCE_EXAMPLE}`;
