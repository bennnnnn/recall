import type { CalendarProposal } from "@/lib/calendarProposal";
import { parseCalendarProposals, stripCalendarProposalFences } from "@/lib/calendarProposal";
import type { SettingsProposal } from "@/lib/settingsProposal";
import { parseSettingsProposals, stripSettingsProposalFences } from "@/lib/settingsProposal";
import { stripReminderFences } from "@/lib/todos/reminderFence";
import type { SearchSource } from "@/lib/api";
import {
  hasVocabQuizFence,
  isRenderableVocabQuiz,
  parseVocabQuiz,
  stripVocabQuizBlock,
  stripVocabQuizPrologue,
  stripVocabSessionMetadata,
  type ParsedVocabQuiz,
} from "@/lib/projects/parseVocabQuiz";
import { hasVocabCardFence, stripVocabCardBlock } from "@/lib/projects/parseVocabCard";
import {
  hasLearningLaunchFence,
  parseLearningLaunch,
  stripLearningLaunchBlock,
  type ParsedLearningLaunch,
} from "@/lib/projects/parseLearningLaunch";

import { isLocationQuestion } from "@/lib/localPlacesQuery";
import { resolvePlaces, stripPlacesContent, type PlaceItem } from "@/lib/placesList";
import { resolveSearchSources, stripSearchSourcesFromContent } from "@/lib/searchSources";
import { parseMessageImages, stripLookupSourceCaption, type ParsedMessageImage } from "@/lib/messageAttachments";
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
};

export type AssistantMessageContent = {
  hasContent: boolean;
  showActionSlot: boolean;
  actionsReady: boolean;
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
    showPlaces,
    places,
  } = options;

  // The strips below are fence-scoped — a reply with no fences and no quiz
  // (the common case) skips ~8 full-content regex passes per derive, keeping
  // only the chain's whitespace normalization (trim + collapse 3+ newlines).
  const hasFence = content.includes("```");
  if (!hasFence && !quizForStrip) {
    return content.replace(/\n{3,}/g, "\n\n").trim();
  }

  let text = hideCardFenceInMarkdown
    ? stripVocabCardBlock(hideQuizFenceInMarkdown ? stripVocabQuizBlock(content) : content)
    : hideQuizFenceInMarkdown
      ? stripVocabQuizBlock(content)
      : stripVocabSessionMetadata(content);

  if (quizForStrip && isRenderableVocabQuiz(quizForStrip)) {
    if (!hideQuizFenceInMarkdown) {
      text = stripVocabQuizBlock(content);
    }
    text = stripVocabQuizPrologue(text, quizForStrip);
  }

  if (!hasFence) return text;

  if (showLiveClock) text = stripTimeAnswerFences(text);
  text = stripLearningLaunchBlock(text);
  text = stripSearchSourcesFromContent(text);
  text = stripReminderFences(text);
  text = stripCalendarProposalFences(text);
  text = stripSettingsProposalFences(text);
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
  } = input;

  const hasContent = content.trim().length > 0;
  const showActionSlot = !isUser && hasContent;
  // Mount only after generation ends. While streaming, composer-gap pad holds
  // the same height so the prose does not move when icons appear (ChatGPT).
  const actionsReady = showActionSlot && !isGenerating;

  // Defer the expensive quiz parse (its markdown fallback scans line-by-line)
  // until the stream settles — the fence itself is still hidden mid-stream via
  // hideQuizFenceInMarkdown; only the prologue strip waits for settle.
  const quizForStrip =
    isUser || !hasContent || isGenerating
      ? null
      : (() => {
          const quiz = parseVocabQuiz(content);
          return isRenderableVocabQuiz(quiz) ? quiz : null;
        })();

  const hideQuizFenceInMarkdown = hasVocabQuizFence(content) || Boolean(quizForStrip);
  const hideCardFenceInMarkdown = hideQuizFenceInMarkdown || hasVocabCardFence(content);

  const showLiveClock =
    !isUser &&
    hasContent &&
    !layoutFrozen &&
    assistantReplyIsTimeAnswer(content, priorUserText);

  const clockTimezone = showLiveClock ? extractClockTimezone(content) : "";
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

  // [Image: …] marker lines only appear in attachment/lookup replies — skip the
  // per-line split+regex scan for the common no-marker reply.
  const parsedImages =
    !isUser && hasContent && content.includes("[Image:")
      ? parseMessageImages(content)
      : { images: [], textWithoutImages: content };
  const showImages = parsedImages.images.length > 0 && !layoutFrozen;
  const proseWithoutImages =
    parsedImages.images.length > 0
      ? stripLookupSourceCaption(parsedImages.textWithoutImages)
      : parsedImages.textWithoutImages;

  const markdownContent = buildMarkdownContent({
    content: proseWithoutImages,
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
    !showCalendarProposals &&
    !(priorUserText != null && isLocationQuestion(priorUserText));

  const learningLaunch =
    !isUser && !layoutFrozen && hasLearningLaunchFence(content)
      ? parseLearningLaunch(content)
      : null;

  return {
    hasContent,
    showActionSlot,
    actionsReady,
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
    markdownStreamMode: layoutFrozen || isGenerating,
    markdownResetKey: `${renderKey ?? messageId}:${markdownContent.length}`,
    learningLaunch,
  };
}
