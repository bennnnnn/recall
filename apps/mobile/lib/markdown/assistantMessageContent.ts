import type { SettingsProposal } from "@/lib/settingsProposal";
import { parseSettingsProposals, stripSettingsProposalFences } from "@/lib/settingsProposal";
import { stripReminderFences } from "@/features/todos/model/reminderFence";
import { hasTodoLink, stripTodoLinkFences } from "@/features/todos/model/todoLink";
import type { SearchSource } from "@/lib/api";

import { isLocationQuestion } from "@/lib/places/localPlacesQuery";
import { resolveSearchSources, stripSearchSourcesFromContent } from "@/lib/searchSources";
import { parseMessageImages, stripLookupSourceCaption, type ParsedMessageImage } from "@/lib/messageAttachments";
import { parseFenceLang } from "@/lib/codeHighlight";
import { mapClosedFences } from "@/lib/fence/scan";
import {
  assistantReplyIsTimeAnswer,
  extractClockTimezone,
  stripTimeAnswerFences,
} from "@/lib/timeQuestion";

type AssistantMessageContentInput = {
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
  settingsProposals: SettingsProposal[];
  showSettingsProposals: boolean;
  /** A to-do change asked in chat: the Open To-do button (todoLink.ts). */
  showTodoLink: boolean;
  /**
   * The reply was only an old reminder card (chat no longer offers one): it reads as the
   * line chat says now, with the button, never an empty bubble.
   */
  oldReminderCardOnly: boolean;
  images: ParsedMessageImage[];
  showImages: boolean;
  markdownContent: string;
  hasMarkdown: boolean;
  showSearchSources: boolean;
  markdownStreamMode: boolean;
  markdownResetKey: string;
};

/**
 * Stored chats may still contain retired product fences (the language-learning
 * cards, the Google Calendar event proposal, the places card a reply's linked names
 * replaced, and the chat reminder card: chat only reads to-dos, both 2026-11-27).
 * Drop the JSON.
 */
const RETIRED_FENCE_LANGS: ReadonlySet<string> = new Set([
  "vocab_quiz",
  "vocab_card",
  "learning_launch",
  "job-results",
  "calendar_proposal",
  "places",
  "reminder_proposal",
]);

/** One empty list, so a frozen reply's sources keep their identity flush to flush. */
const NO_SOURCES: SearchSource[] = [];

const UNVERIFIED_RESULT_LINE =
  /[ \t]*\*?I couldn't automatically verify this result\.\*?[ \t]*/g;

function stripUnverifiedResultLine(text: string): string {
  if (!text.includes("automatically verify this result")) return text;
  return text.replace(UNVERIFIED_RESULT_LINE, "").replace(/\n{3,}/g, "\n\n").trim();
}

/** An old saved reply's reminder card: shown as the To-do line and button instead. */
const OLD_REMINDER_CARD = /```reminder_proposal\b/i;

/** Any retired name in any case: a fence's language is read lower-cased. */
const RETIRED_FENCE_NAME = new RegExp([...RETIRED_FENCE_LANGS].join("|"), "i");

/** The retired places card's fields (`name`, `url`, `note`, `address`, `price`). */
const PLACES_CARD_KEYS: ReadonlySet<string> = new Set(["name", "url", "note", "address", "price"]);

/**
 * A ```json fence holding the retired places card's venue list, as models once wrote it in
 * place of the card (`[{"name":"Shell","url":…}]`, 2026-11-08): every row the card's fields
 * alone, with a name and an address to open. JSON with any other field stays as written.
 */
function isRetiredVenueList(body: string): boolean {
  let parsed: unknown;
  try {
    parsed = JSON.parse(body);
  } catch (error) {
    if (error instanceof SyntaxError) return false;
    throw error;
  }
  if (!Array.isArray(parsed) || parsed.length === 0) return false;
  return parsed.every((row: unknown) => {
    if (!row || typeof row !== "object" || Array.isArray(row)) return false;
    const fields = row as Record<string, unknown>;
    const onlyCardFields = Object.keys(fields).every((key) => PLACES_CARD_KEYS.has(key));
    return onlyCardFields && typeof fields.name === "string" && typeof fields.url === "string";
  });
}

function stripRetiredFences(text: string): string {
  // Only old stored chats hold one; every other reply skips the line walk.
  if (!text.includes("```")) return text;
  if (!/```json/i.test(text) && !RETIRED_FENCE_NAME.test(text)) return text;
  return mapClosedFences(text, (info, body, original) => {
    const lang = parseFenceLang(info);
    if (RETIRED_FENCE_LANGS.has(lang)) return "";
    return lang === "json" && isRetiredVenueList(body) ? "" : original;
  });
}

/**
 * The reply's markdown, its control fences stripped.
 */
function buildMarkdownContent(options: {
  content: string;
  showLiveClock: boolean;
}): string {
  const { content, showLiveClock } = options;

  // Fence-scoped strips — a reply with no fences skips the regex passes and
  // only normalizes whitespace.
  const hasFence = content.includes("```");
  if (!hasFence) {
    return content.replace(/\n{3,}/g, "\n\n").trim();
  }

  let text = stripRetiredFences(content);
  if (showLiveClock) text = stripTimeAnswerFences(text);
  text = stripSearchSourcesFromContent(text);
  text = stripReminderFences(text);
  text = stripSettingsProposalFences(text);
  return stripTodoLinkFences(text);
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

  const showLiveClock =
    !isUser &&
    hasContent &&
    !layoutFrozen &&
    assistantReplyIsTimeAnswer(content);

  const clockTimezone = showLiveClock ? extractClockTimezone(content) : "";
  // While the layout is frozen the Sources row is hidden, and a reply's own
  // sources fence comes at its end: reading the fence waits until then.
  const attachedSources = liveSearchSources ?? storedSearchSources;
  const searchSources = layoutFrozen
    ? attachedSources ?? NO_SOURCES
    : resolveSearchSources(content, attachedSources);

  const settingsProposals =
    !isUser && hasContent && !layoutFrozen ? parseSettingsProposals(content) : [];
  const showSettingsProposals = settingsProposals.length > 0 && !layoutFrozen;

  const oldReminderCard = !isUser && hasContent && OLD_REMINDER_CARD.test(content);
  const showTodoLink =
    !isUser && hasContent && !layoutFrozen && (hasTodoLink(content) || oldReminderCard);

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

  const proseForMarkdown = isUser
    ? proseWithoutImages
    : stripUnverifiedResultLine(proseWithoutImages);

  const markdownContent = buildMarkdownContent({
    content: proseForMarkdown,
    showLiveClock,
  });

  const hasMarkdown = markdownContent.trim().length > 0;
  const oldReminderCardOnly = oldReminderCard && !hasMarkdown;
  // Live clock and "where am I" are device-driven — a Sources chip would
  // imply the answer came from those links, which it didn't.
  const showSearchSources =
    searchSources.length > 0 &&
    !layoutFrozen &&
    !showLiveClock &&
    !(priorUserText != null && isLocationQuestion(priorUserText));

  return {
    hasContent,
    showActionSlot,
    actionsReady,
    showLiveClock,
    clockTimezone,
    searchSources,
    settingsProposals,
    showSettingsProposals,
    showTodoLink,
    oldReminderCardOnly,
    images: parsedImages.images,
    showImages,
    markdownContent,
    hasMarkdown,
    showSearchSources,
    markdownStreamMode: layoutFrozen || isGenerating,
    markdownResetKey: `${renderKey ?? messageId}:${markdownContent.length}`,
  };
}
