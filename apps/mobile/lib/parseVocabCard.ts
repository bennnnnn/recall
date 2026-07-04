export type ParsedVocabCard = {
  word: string;
  partOfSpeech?: string;
  definition: string;
  exampleSentence?: string;
};

const VOCAB_CARD_FENCE_RE = /```vocab_card\s*\n([\s\S]*?)```/i;
const VOCAB_CARD_FENCE_PARTIAL_RE = /```vocab_card[\s\S]*$/i;

export function parseVocabCard(content: string): ParsedVocabCard | null {
  const match = content.match(VOCAB_CARD_FENCE_RE);
  if (!match?.[1]) return null;
  try {
    const raw = JSON.parse(match[1].trim()) as Record<string, unknown>;
    const word = String(raw.word ?? "").trim();
    const definition = String(raw.definition ?? "").trim();
    if (!word || !definition) return null;
    const partOfSpeech =
      typeof raw.part_of_speech === "string" ? raw.part_of_speech.trim() : undefined;
    const exampleSentence =
      typeof raw.example_sentence === "string" ? raw.example_sentence.trim() : undefined;
    return { word, partOfSpeech, definition, exampleSentence };
  } catch {
    return null;
  }
}

export function hasVocabCardFence(content: string): boolean {
  return VOCAB_CARD_FENCE_RE.test(content) || VOCAB_CARD_FENCE_PARTIAL_RE.test(content);
}

export function stripVocabCardBlock(content: string): string {
  return content.replace(VOCAB_CARD_FENCE_RE, "").replace(VOCAB_CARD_FENCE_PARTIAL_RE, "").trim();
}
