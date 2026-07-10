/** Shared quiz card format — keep in sync with apps/api/app/services/projects.py */

export const VOCAB_QUIZ_MARKDOWN_EXAMPLE = [
  "**Word:** apple",
  "What does it mean?",
  "A) a red fruit",
  "B) a vehicle",
  "C) a feeling",
  "D) a color",
].join("\n");

export const VOCAB_QUIZ_FENCE_EXAMPLE = [
  "```vocab_quiz",
  JSON.stringify({
    word: "apple",
    question: "What does it mean?",
    correct: "A",
    choices: [
      { letter: "A", text: "a red fruit" },
      { letter: "B", text: "a vehicle" },
      { letter: "C", text: "a feeling" },
      { letter: "D", text: "a color" },
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
