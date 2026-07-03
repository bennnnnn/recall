import React, { useEffect, useMemo, useRef, useState } from "react";
import * as Clipboard from "expo-clipboard";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { CalendarProposalCard } from "@/components/CalendarProposalCard";
import { PlacesListBlock } from "@/components/PlacesListBlock";
import { CollapsibleMessageBody } from "@/components/CollapsibleMessageBody";
import { UserMessageContent } from "@/components/UserMessageContent";
import { SearchSourcesStack } from "@/components/SearchSourcesStack";
import { CircularClockBlock } from "@/components/rich/CircularClockBlock";
import { MarkdownContent } from "@/components/MarkdownContent";
import { StreamingCursor } from "@/components/StreamingCursor";
import { MarkdownErrorBoundary } from "@/components/MarkdownErrorBoundary";
import { RecallTypingIndicator } from "@/components/RecallTypingIndicator";
import { VocabQuizChoices } from "@/components/VocabQuizChoices";
import { Message } from "@/lib/api";
import {
  parseCalendarProposals,
  stripCalendarProposalFences,
} from "@/lib/calendarProposal";
import { extractPrimaryCopyText } from "@/lib/copyBlock";
import { notifySuccess, notifyWarning, tap } from "@/lib/haptics";
import { parseVocabQuiz, stripVocabQuizBlock, isCompleteVocabQuiz, hasVocabQuizFence, cleanQuizWord, stripQuizMarkdownDuplicates, type QuizAnswerMeta } from "@/lib/parseVocabQuiz";
import { resolvePlaces, stripPlacesContent } from "@/lib/placesList";
import {
  resolveSearchSources,
  stripSearchSourcesFromContent,
} from "@/lib/searchSources";
import {
  assistantReplyIsTimeAnswer,
  extractClockTimezone,
  stripTimeAnswerFences,
} from "@/lib/timeQuestion";
import { SENDING_LABEL_DELAY_MS } from "@/lib/chatMessageLogic";
import { STREAM_LAYOUT_SETTLE_MS } from "@/lib/messageListLayout";
import { useRotatingStreamStatus } from "@/lib/streamStatusLabel";
import { Theme, useTheme } from "@/lib/theme";
import { useTranslation } from "react-i18next";

type Props = {
  message: Message;
  priorUserText?: string | null;
  isGenerating?: boolean;
  /** Live token stream — avoids mutating the messages array on every token. */
  liveContent?: string;
  liveSearchSources?: Message["search_sources"];
  streamStatus?: string;
  isLastAssistant?: boolean;
  onRegenerate?: () => void;
  onEdit?: (message: Message) => void;
  canEdit?: boolean;
  onFeedback?: (messageId: string, feedback: "up" | "down" | null) => void;
  onQuizAnswer?: (
    messageId: string,
    letter: "A" | "B" | "C" | "D",
    meta?: QuizAnswerMeta,
  ) => void;
  quizDisabled?: boolean;
  quizLanguage?: string;
  quizVariant?: "vocab" | "trivia";
  quizSelectedLetter?: "A" | "B" | "C" | "D" | null;
  highlighted?: boolean;
  isSending?: boolean;
};

async function copyText(text: string) {
  await Clipboard.setStringAsync(text);
}

function AssistantActions({
  messageId,
  content,
  feedback,
  onFeedback,
  onRegenerate,
  theme,
  hidden = false,
}: {
  messageId: string;
  content: string;
  feedback: "up" | "down" | null;
  onFeedback?: (messageId: string, feedback: "up" | "down" | null) => void;
  onRegenerate?: () => void;
  theme: Theme;
  hidden?: boolean;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    tap();
    await copyText(content);
    setCopied(true);
    notifySuccess();
    setTimeout(() => setCopied(false), 1500);
  };

  const rate = (dir: "up" | "down") => {
    const next = feedback === dir ? null : dir;
    onFeedback?.(messageId, next);
    if (next === "up") notifySuccess();
    else if (next === "down") notifyWarning();
    else tap();
  };

  return (
    <View style={[a.row, hidden && a.rowHidden]} pointerEvents={hidden ? "none" : "auto"}>
      <Pressable
        style={a.btn}
        onPress={handleCopy}
        hitSlop={8}
        disabled={!content.trim()}
      >
        <Ionicons
          name={copied ? "checkmark-outline" : "copy-outline"}
          size={19}
          color={copied ? theme.primary : theme.textSecondary}
        />
      </Pressable>
      <Pressable style={a.btn} onPress={() => rate("up")} hitSlop={8}>
        <Ionicons
          name={feedback === "up" ? "thumbs-up" : "thumbs-up-outline"}
          size={19}
          color={feedback === "up" ? theme.primary : theme.textSecondary}
        />
      </Pressable>
      <Pressable style={a.btn} onPress={() => rate("down")} hitSlop={8}>
        <Ionicons
          name={feedback === "down" ? "thumbs-down" : "thumbs-down-outline"}
          size={19}
          color={feedback === "down" ? theme.primary : theme.textSecondary}
        />
      </Pressable>
      {onRegenerate && (
        <Pressable
          style={a.btn}
          onPress={() => {
            tap();
            onRegenerate();
          }}
          hitSlop={8}
        >
          <Ionicons name="refresh-outline" size={19} color={theme.textSecondary} />
        </Pressable>
      )}
    </View>
  );
}

export const MessageBubble = React.memo(function MessageBubble({
  message,
  priorUserText = null,
  isGenerating = false,
  liveContent,
  liveSearchSources,
  streamStatus,
  isLastAssistant,
  onRegenerate,
  onEdit,
  canEdit,
  onFeedback,
  onQuizAnswer,
  quizDisabled,
  quizLanguage = "en",
  quizVariant = "vocab",
  quizSelectedLetter = null,
  highlighted = false,
  isSending = false,
}: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const b = useMemo(() => makeStyles(theme), [theme]);
  const [showSendingLabel, setShowSendingLabel] = useState(false);
  const [holdStreamLayout, setHoldStreamLayout] = useState(false);
  const wasGeneratingRef = useRef(false);

  useEffect(() => {
    if (isGenerating) {
      wasGeneratingRef.current = true;
      setHoldStreamLayout(false);
      return;
    }
    if (!wasGeneratingRef.current) return;
    wasGeneratingRef.current = false;
    setHoldStreamLayout(true);
    const timer = setTimeout(() => setHoldStreamLayout(false), STREAM_LAYOUT_SETTLE_MS);
    return () => clearTimeout(timer);
  }, [isGenerating]);

  useEffect(() => {
    if (!isSending) {
      setShowSendingLabel(false);
      return;
    }
    const timer = setTimeout(() => setShowSendingLabel(true), SENDING_LABEL_DELAY_MS);
    return () => clearTimeout(timer);
  }, [isSending]);
  const isUser = message.role === "user";
  const isStreaming = isGenerating;
  const layoutFrozen = isStreaming || holdStreamLayout;
  const content = liveContent ?? message.content;
  const hasContent = content.trim().length > 0;
  const statusLabel = useRotatingStreamStatus(
    streamStatus,
    isStreaming && !hasContent,
    t,
  );
  const showActions = !isUser && hasContent && !layoutFrozen;
  const reserveActionRow = !isUser && hasContent && layoutFrozen;
  const quiz = useMemo(() => {
    if (isUser || !hasContent) return null;
    const parsed = parseVocabQuiz(content);
    return isCompleteVocabQuiz(parsed) ? parsed : null;
  }, [isUser, hasContent, content]);
  const quizVariantResolved =
    quizVariant === "trivia" || quiz?.quizType === "trivia" ? "trivia" : "vocab";
  const quizTopicLabel = quiz ? cleanQuizWord(quiz.word) : "";
  const quizQuestionText = quiz
    ? quizVariantResolved === "trivia"
      ? quiz.question?.trim() || quizTopicLabel
      : quiz.question?.trim() || ""
    : "";
  const showQuizCard = quiz != null && !layoutFrozen;
  const hideQuizFenceInMarkdown = showQuizCard || hasVocabQuizFence(content);
  const showQuizButtons =
    showQuizCard && isLastAssistant && onQuizAnswer != null;
  const showLiveClock =
    !isUser &&
    hasContent &&
    !layoutFrozen &&
    assistantReplyIsTimeAnswer(content, priorUserText ?? null);
  const clockTimezone = useMemo(
    () => extractClockTimezone(content),
    [content],
  );
  const searchSources = useMemo(
    () =>
      resolveSearchSources(
        content,
        liveSearchSources ?? message.search_sources,
      ),
    [content, liveSearchSources, message.search_sources],
  );
  const calendarProposals = useMemo(
    () =>
      !isUser && hasContent && !layoutFrozen
        ? parseCalendarProposals(content)
        : [],
    [isUser, hasContent, layoutFrozen, content],
  );
  const showCalendarProposals = calendarProposals.length > 0 && !layoutFrozen;
  const places = useMemo(
    () => (!isUser && hasContent && !layoutFrozen ? resolvePlaces(content) : []),
    [isUser, hasContent, layoutFrozen, content],
  );
  const showPlaces = places.length > 0;
  const markdownContent = useMemo(() => {
    let text = hideQuizFenceInMarkdown ? stripVocabQuizBlock(content) : content;
    if (showQuizCard && quiz) {
      text = stripQuizMarkdownDuplicates(text, quiz);
    }
    if (showLiveClock) text = stripTimeAnswerFences(text);
    text = stripSearchSourcesFromContent(text);
    if (showCalendarProposals) text = stripCalendarProposalFences(text);
    if (showPlaces) text = stripPlacesContent(text, places);
    return text;
  }, [hideQuizFenceInMarkdown, showQuizCard, quiz, showLiveClock, showCalendarProposals, showPlaces, places, content]);
  const hasMarkdown = markdownContent.trim().length > 0;
  const showSearchSources =
    searchSources.length > 0 &&
    !layoutFrozen &&
    !showLiveClock &&
    !showQuizCard &&
    !showCalendarProposals;
  const showContextSummarized =
    !isUser && !layoutFrozen && (message.context_summarized ?? 0) > 0;
  const markdownStreamMode = layoutFrozen;
  const markdownResetKey = `${message.renderKey ?? message.id}:${markdownContent.length}`;

  return (
    <View style={[b.row, isUser ? b.userRow : b.assistantRow, highlighted && b.rowHighlighted]}>
      {isUser ? (
        <View style={b.userColumn}>
          <UserMessageContent message={message} />
          {showSendingLabel ? (
            <Text style={b.sendingLabel}>{t("chat.sending")}</Text>
          ) : null}
          {canEdit && onEdit && !message.id.startsWith("local-") ? (
            <Pressable style={b.editBtn} onPress={() => onEdit(message)} hitSlop={8}>
              <Ionicons name="pencil-outline" size={16} color={theme.textTertiary} />
            </Pressable>
          ) : null}
        </View>
      ) : (
        <View style={b.assistantBubble}>
          <CollapsibleMessageBody enabled={!layoutFrozen && hasContent} collapsible={false}>
            {isStreaming && !hasContent ? (
              <View style={b.waitingWrap}>
                <RecallTypingIndicator />
                {statusLabel ? <Text style={b.statusLabel}>{statusLabel}</Text> : null}
              </View>
            ) : null}
            {showContextSummarized ? (
              <Text style={b.contextChip}>
                {t("chat.context_summarized", { count: message.context_summarized })}
              </Text>
            ) : null}
            {showLiveClock ? (
              <CircularClockBlock content={clockTimezone} />
            ) : null}
            {hasMarkdown ? (
              <MarkdownErrorBoundary
                resetKey={markdownResetKey}
                content={markdownContent}
              >
                <MarkdownContent content={markdownContent} streaming={markdownStreamMode} />
                {isStreaming && hasMarkdown ? <StreamingCursor /> : null}
              </MarkdownErrorBoundary>
            ) : null}
            {showPlaces ? <PlacesListBlock places={places} /> : null}
            {showQuizCard && quiz ? (
              <VocabQuizChoices
                quiz={quiz}
                variant={quizVariant === "trivia" || quiz.quizType === "trivia" ? "trivia" : "vocab"}
                disabled={!showQuizButtons || !!quizDisabled}
                language={quizLanguage}
                initialSelected={quizSelectedLetter}
                onSelect={
                  showQuizButtons && onQuizAnswer
                    ? (letter) => {
                        const isCorrect =
                          quiz.correct != null ? letter === quiz.correct : null;
                        onQuizAnswer(message.id, letter, {
                          topic: quizTopicLabel,
                          question: quizQuestionText,
                          isCorrect,
                        });
                      }
                    : undefined
                }
              />
            ) : null}
            {showCalendarProposals
              ? calendarProposals.map((proposal, index) => (
                  <CalendarProposalCard
                    key={`${proposal.proposal_id ?? proposal.title}-${index}`}
                    proposal={proposal}
                    disabled={!isLastAssistant}
                  />
                ))
              : null}
            {showSearchSources ? <SearchSourcesStack sources={searchSources} /> : null}
          </CollapsibleMessageBody>
        </View>
      )}

      {(showActions || reserveActionRow) && (
        <View style={reserveActionRow && !showActions ? b.actionRowReserved : undefined}>
          <AssistantActions
            messageId={message.id}
            content={extractPrimaryCopyText(content)}
            feedback={message.feedback ?? null}
            onFeedback={onFeedback}
            onRegenerate={isLastAssistant ? onRegenerate : undefined}
            theme={theme}
            hidden={reserveActionRow && !showActions}
          />
        </View>
      )}
    </View>
  );
});

const a = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
    marginTop: 4,
    marginLeft: 2,
  },
  rowHidden: {
    opacity: 0,
  },
  btn: {
    width: 34,
    height: 34,
    alignItems: "center",
    justifyContent: "center",
  },
});

function makeStyles(t: Theme) {
  return StyleSheet.create({
    row: { marginVertical: 4, paddingHorizontal: 16 },
    rowHighlighted: {
      backgroundColor: t.primaryLight,
      borderRadius: 12,
      marginHorizontal: 8,
      paddingHorizontal: 8,
    },
    userRow: { alignItems: "flex-end" },
    userColumn: { alignItems: "flex-end", maxWidth: "88%" },
    sendingLabel: {
      marginTop: 4,
      marginRight: 4,
      fontSize: 13,
      color: t.textTertiary,
    },
    editBtn: { marginTop: 2, marginRight: 4, padding: 4 },
    assistantRow: { alignItems: "stretch" },
    assistantBubble: {
      maxWidth: "100%",
      backgroundColor: "transparent",
      paddingVertical: 2,
    },
    waitingWrap: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      paddingVertical: 4,
    },
    statusLabel: {
      fontSize: 14,
      color: t.textTertiary,
    },
    userText: { color: t.userText, fontSize: 16, lineHeight: 23 },
    streamingText: { color: t.assistantText, fontSize: 16, lineHeight: 25 },
    contextChip: {
      fontSize: 12,
      lineHeight: 16,
      color: t.textTertiary,
      marginBottom: 6,
    },
    actionRowReserved: {
      minHeight: 38,
    },
  });
}
