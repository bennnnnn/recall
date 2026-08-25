import type { CalendarProposal } from "@/lib/calendarProposal";
import { parseCalendarProposals, stripCalendarProposalFences } from "@/lib/calendarProposal";
import type { SettingsProposal } from "@/lib/settingsProposal";
import { parseSettingsProposals, stripSettingsProposalFences } from "@/lib/settingsProposal";
import { stripReminderFences } from "@/lib/reminderFence";
import type { SearchSource } from "@/lib/api";
import {
  formatVocabQuizPromptOnly,
  hasVocabQuizFence,
  isRenderableVocabQuiz,
  parseVocabQuiz,
  stripVocabQuizBlock,
  stripVocabQuizPrologue,
  stripVocabSessionMetadata,
  type ParsedVocabQuiz,
} from "@/lib/parseVocabQuiz";
import {
  hasVocabCardFence,
  parseVocabCard,
  stripVocabCardBlock,
  type ParsedVocabCard,
} from "@/lib/parseVocabCard";
import {
  hasLearningLaunchFence,
  parseLearningLaunch,
  stripLearningLaunchBlock,
  type ParsedLearningLaunch,
} from "@/lib/parseLearningLaunch";

/** True when the assistant is asking the user to produce a sentence (teach→use). */
function asksUserToWriteSentence(content: string): boolean {
  return /write (?:your own |a |an )?sentence|use .+ in (?:a |your own )?sentence/i.test(
    content,
  );
}
import { isLocationQuestion } from "@/lib/localPlacesQuery";
import { resolvePlaces, stripPlacesContent, type PlaceItem } from "@/lib/placesList";
import { resolveSearchSources, stripSearchSourcesFromContent } from "@/lib/searchSources";
import { parseMessageImages, type ParsedMessageImage } from "@/lib/messageAttachments";
import {
  assistantReplyIsTimeAnswer,
  extractClockTimezone,
  stripTimeAnswerFences,
} from "@/lib/timeQuestion";

export type AssistantMessageContentInput = {
  content: string;
  layoutFrozen: boolean;
  isUser: boolean;
  priorUserText: string | null;
  storedSearchSources?: SearchSource[];
  liveSearchSources?: SearchSource[];
  messageId: string;
  isGenerating: boolean;
  renderKey?: string;
  /** True if this message was ever in streaming mode — keeps the chunked
   *  renderer active after the settle hold ends to avoid a full remount. */
  wasStreamed?: boolean;
};

export type AssistantMessageContent = {
  hasContent: boolean;
  isQuizFeedback: boolean;
  showActionSlot: boolean;
  actionsReady: boolean;
  quizForStrip: ParsedVocabQuiz | null;
  vocabCard: ParsedVocabCard | null;
  showVocabCard: boolean;
  showLiveClock: boolean;
  clockTimezone: string;
  searchSources: SearchSource[];
  calendarProposals: CalendarProposal[];
  showCalendarProposals: boolean;
  settingsProposals: SettingsProposal[];
  showSettingsProposals: boolean;
  places: PlaceItem[];
  showPlaces: boolean;
  images: ParsedMessageImage[];
  showImages: boolean;
  markdownContent: string;
  hasMarkdown: boolean;
  showSearchSources: boolean;
  markdownStreamMode: boolean;
  markdownResetKey: string;
  interactiveQuiz: ParsedVocabQuiz | null;
  learningLaunch: ParsedLearningLaunch | null;
};

function buildMarkdownContent(options: {
  content: string;
  hideCardFenceInMarkdown: boolean;
  hideQuizFenceInMarkdown: boolean;
  quizForStrip: ParsedVocabQuiz | null;
  showLiveClock: boolean;
  showCalendarProposals: boolean;
  showSettingsProposals: boolean;
  showPlaces: boolean;
  places: PlaceItem[];
}): string {
  const {
    content,
    hideCardFenceInMarkdown,
    hideQuizFenceInMarkdown,
    quizForStrip,
    showLiveClock,
    showCalendarProposals,
    showSettingsProposals,
    showPlaces,
    places,
  } = options;

  let text = hideCardFenceInMarkdown
    ? stripVocabCardBlock(hideQuizFenceInMarkdown ? stripVocabQuizBlock(content) : content)
    : hideQuizFenceInMarkdown
      ? stripVocabQuizBlock(content)
      : stripVocabSessionMetadata(content);

  if (quizForStrip && isRenderableVocabQuiz(quizForStrip)) {
    // Chips replace A–D — strip list whether it came from a fence or plain markdown.
    if (!hideQuizFenceInMarkdown) {
      text = stripVocabQuizBlock(content);
    }
    text = stripVocabQuizPrologue(text, quizForStrip);
    const quizBody = formatVocabQuizPromptOnly(quizForStrip);
    text = text.trim() ? `${text.trim()}\n\n${quizBody}` : quizBody;
  }

  if (showLiveClock) text = stripTimeAnswerFences(text);
  text = stripLearningLaunchBlock(text);
  text = stripSearchSourcesFromContent(text);
  text = stripReminderFences(text);
  if (showCalendarProposals) text = stripCalendarProposalFences(text);
  if (showSettingsProposals) text = stripSettingsProposalFences(text);
  if (showPlaces) text = stripPlacesContent(text, places);
  return text;
}

/** Pure assistant reply display model — fences stripped, rich blocks resolved. */
export function deriveAssistantMessageContent(
  input: AssistantMessageContentInput,
): AssistantMessageContent {
  const {
    content,
    layoutFrozen,
    isUser,
    priorUserText,
    storedSearchSources,
    liveSearchSources,
    messageId,
    isGenerating,
    renderKey,
    wasStreamed,
  } = input;

  const hasContent = content.trim().length > 0;
  const isQuizFeedback = messageId.startsWith("local-quiz-");
  const showActionSlot = !isUser && hasContent && !isQuizFeedback;
  // Mount only after generation ends. While streaming, composer-gap pad holds
  // the same height so the prose does not move when icons appear (ChatGPT).
  const actionsReady = showActionSlot && !isGenerating;

  const quizForStrip =
    isUser || !hasContent
      ? null
      : (() => {
          const quiz = parseVocabQuiz(content);
          return isRenderableVocabQuiz(quiz) ? quiz : null;
        })();

  const rawVocabCard =
    isUser || !hasContent || quizForStrip ? null : parseVocabCard(content);
  // Teach→use: never show the example sentence before the user writes theirs.
  const vocabCard =
    rawVocabCard && asksUserToWriteSentence(content)
      ? { ...rawVocabCard, exampleSentence: undefined }
      : rawVocabCard;

  const showVocabCard = vocabCard != null && !layoutFrozen;
  const hideQuizFenceInMarkdown = hasVocabQuizFence(content);
  const hideCardFenceInMarkdown =
    hideQuizFenceInMarkdown || showVocabCard || hasVocabCardFence(content);

  const showLiveClock =
    !isUser &&
    hasContent &&
    !layoutFrozen &&
    assistantReplyIsTimeAnswer(content, priorUserText);

  const clockTimezone = extractClockTimezone(content);
  const searchSources = resolveSearchSources(
    content,
    liveSearchSources ?? storedSearchSources,
  );

  const calendarProposals =
    !isUser && hasContent && !layoutFrozen ? parseCalendarProposals(content) : [];
  const showCalendarProposals = calendarProposals.length > 0 && !layoutFrozen;

  const settingsProposals =
    !isUser && hasContent && !layoutFrozen ? parseSettingsProposals(content) : [];
  const showSettingsProposals = settingsProposals.length > 0 && !layoutFrozen;

  const places =
    !isUser && hasContent && !layoutFrozen ? resolvePlaces(content) : [];
  const showPlaces = places.length > 0;

  const parsedImages = !isUser && hasContent ? parseMessageImages(content) : { images: [], textWithoutImages: content };
  const showImages = parsedImages.images.length > 0 && !layoutFrozen;

  const markdownContent = buildMarkdownContent({
    content: parsedImages.textWithoutImages,
    hideCardFenceInMarkdown,
    hideQuizFenceInMarkdown,
    quizForStrip,
    showLiveClock,
    showCalendarProposals,
    showSettingsProposals,
    showPlaces,
    places,
  });

  const hasMarkdown = markdownContent.trim().length > 0;
  // Live clock and "where am I" are device-driven — a Sources chip would
  // imply the answer came from those links, which it didn't.
  const showSearchSources =
    searchSources.length > 0 &&
    !layoutFrozen &&
    !showLiveClock &&
    !hideQuizFenceInMarkdown &&
    !showVocabCard &&
    !showCalendarProposals &&
    !(priorUserText != null && isLocationQuestion(priorUserText));

  const interactiveQuiz =
    !isUser && !layoutFrozen && quizForStrip && isRenderableVocabQuiz(quizForStrip)
      ? quizForStrip
      : null;
  const learningLaunch =
    !isUser && !layoutFrozen && hasLearningLaunchFence(content)
      ? parseLearningLaunch(content)
      : null;

  return {
    hasContent,
    isQuizFeedback,
    showActionSlot,
    actionsReady,
    quizForStrip,
    vocabCard,
    showVocabCard,
    showLiveClock,
    clockTimezone,
    searchSources,
    calendarProposals,
    showCalendarProposals,
    settingsProposals,
    showSettingsProposals,
    places,
    showPlaces,
    images: parsedImages.images,
    showImages,
    markdownContent,
    hasMarkdown,
    showSearchSources,
    markdownStreamMode: layoutFrozen || Boolean(wasStreamed),
    markdownResetKey: `${renderKey ?? messageId}:${markdownContent.length}`,
    interactiveQuiz,
    learningLaunch,
  };
}
