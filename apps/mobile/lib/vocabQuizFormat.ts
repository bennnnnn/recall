/** Shared quiz card format — keep in sync with apps/api/app/services/projects.py */

export const VOCAB_QUIZ_MARKDOWN_EXAMPLE = [
  "**Word:** apple [noun]",
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
    part_of_speech: "noun",
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

export const VOCAB_QUIZ_FORMAT_BLOCK = `${VOCAB_QUIZ_MARKDOWN_EXAMPLE}\n\nThen append this machine-readable block (required — include correct letter A–D):\n${VOCAB_QUIZ_FENCE_EXAMPLE}`;
