import type { CalendarProposal } from "@/lib/calendarProposal";
import { parseCalendarProposals, stripCalendarProposalFences } from "@/lib/calendarProposal";
import type { SearchSource } from "@/lib/api";
import {
  formatVocabQuizAsMarkdown,
  hasVocabQuizFence,
  isCompleteVocabQuiz,
  isRenderableVocabQuiz,
  markdownHasQuizChoices,
  parseVocabQuiz,
  stripQuizMarkdownDuplicates,
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
  contextSummarized?: number;
  messageId: string;
  isGenerating: boolean;
  renderKey?: string;
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
  places: PlaceItem[];
  showPlaces: boolean;
  images: ParsedMessageImage[];
  showImages: boolean;
  markdownContent: string;
  hasMarkdown: boolean;
  showSearchSources: boolean;
  showContextSummarized: boolean;
  markdownStreamMode: boolean;
  markdownResetKey: string;
};

function buildMarkdownContent(options: {
  content: string;
  hideCardFenceInMarkdown: boolean;
  hideQuizFenceInMarkdown: boolean;
  quizForStrip: ParsedVocabQuiz | null;
  showLiveClock: boolean;
  showCalendarProposals: boolean;
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
    showPlaces,
    places,
  } = options;

  let text = hideCardFenceInMarkdown
    ? stripVocabCardBlock(hideQuizFenceInMarkdown ? stripVocabQuizBlock(content) : content)
    : hideQuizFenceInMarkdown
      ? stripVocabQuizBlock(content)
      : stripVocabSessionMetadata(content);

  if (quizForStrip && isRenderableVocabQuiz(quizForStrip)) {
    if (isCompleteVocabQuiz(quizForStrip)) {
      text = stripVocabQuizPrologue(text, quizForStrip);
      const quizBody = formatVocabQuizAsMarkdown(quizForStrip);
      text = text.trim() ? `${text.trim()}\n\n${quizBody}` : quizBody;
    } else {
      text = stripQuizMarkdownDuplicates(text, quizForStrip);
      if (!markdownHasQuizChoices(text, quizForStrip)) {
        const quizBody = formatVocabQuizAsMarkdown(quizForStrip);
        text = text.trim() ? `${text.trim()}\n\n${quizBody}` : quizBody;
      }
    }
  }

  if (showLiveClock) text = stripTimeAnswerFences(text);
  text = stripSearchSourcesFromContent(text);
  if (showCalendarProposals) text = stripCalendarProposalFences(text);
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
    contextSummarized,
    messageId,
    isGenerating,
    renderKey,
  } = input;

  const hasContent = content.trim().length > 0;
  const isQuizFeedback = messageId.startsWith("local-quiz-");
  const showActionSlot = !isUser && hasContent && !isQuizFeedback;
  const actionsReady = showActionSlot && !isGenerating;

  const quizForStrip =
    isUser || !hasContent || !hasVocabQuizFence(content)
      ? null
      : (() => {
          const quiz = parseVocabQuiz(content);
          return isRenderableVocabQuiz(quiz) ? quiz : null;
        })();

  const vocabCard =
    isUser || !hasContent || quizForStrip ? null : parseVocabCard(content);

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
    showPlaces,
    places,
  });

  const hasMarkdown = markdownContent.trim().length > 0;
  const showSearchSources =
    searchSources.length > 0 &&
    !layoutFrozen &&
    !showLiveClock &&
    !hideQuizFenceInMarkdown &&
    !showVocabCard &&
    !showCalendarProposals;

  const showContextSummarized =
    !isUser && !layoutFrozen && (contextSummarized ?? 0) > 0;

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
    places,
    showPlaces,
    images: parsedImages.images,
    showImages,
    markdownContent,
    hasMarkdown,
    showSearchSources,
    showContextSummarized,
    markdownStreamMode: layoutFrozen,
    markdownResetKey: `${renderKey ?? messageId}:${markdownContent.length}`,
  };
}
