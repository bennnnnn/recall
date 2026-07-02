import React, { useEffect, useMemo, useState } from "react";
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
import { parseVocabQuiz, stripVocabQuizBlock, isCompleteVocabQuiz } from "@/lib/parseVocabQuiz";
import { resolvePlaces, stripPlacesContent } from "@/lib/placesList";
import {
  resolveSearchSources,
  stripSearchSourcesFence,
} from "@/lib/searchSources";
import {
  assistantReplyIsTimeAnswer,
  extractClockTimezone,
  stripTimeAnswerFences,
} from "@/lib/timeQuestion";
import { shouldCollapseMessage } from "@/lib/messageFold";
import { SENDING_LABEL_DELAY_MS } from "@/lib/chatMessageLogic";
import { Theme, useTheme } from "@/lib/theme";
import { useTranslation } from "react-i18next";

type Props = {
  message: Message;
  priorUserText?: string | null;
  isGenerating?: boolean;
  /** Live token stream — avoids mutating the messages array on every token. */
  liveContent?: string;
  liveSearchSources?: Message["search_sources"];
  isLastAssistant?: boolean;
  onRegenerate?: () => void;
  onEdit?: (message: Message) => void;
  canEdit?: boolean;
  onFeedback?: (messageId: string, feedback: "up" | "down" | null) => void;
  onQuizAnswer?: (messageId: string, letter: "A" | "B" | "C" | "D") => void;
  quizDisabled?: boolean;
  quizLanguage?: string;
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
}: {
  messageId: string;
  content: string;
  feedback: "up" | "down" | null;
  onFeedback?: (messageId: string, feedback: "up" | "down" | null) => void;
  onRegenerate?: () => void;
  theme: Theme;
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
    <View style={a.row}>
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
  isLastAssistant,
  onRegenerate,
  onEdit,
  canEdit,
  onFeedback,
  onQuizAnswer,
  quizDisabled,
  quizLanguage = "en",
  quizSelectedLetter = null,
  highlighted = false,
  isSending = false,
}: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const b = useMemo(() => makeStyles(theme), [theme]);
  const [showSendingLabel, setShowSendingLabel] = useState(false);

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
  const content = liveContent ?? message.content;
  const hasContent = content.trim().length > 0;
  const showActions = !isUser && hasContent && !isStreaming;
  const quiz = useMemo(() => {
    if (isUser || !hasContent) return null;
    const parsed = parseVocabQuiz(content);
    return isCompleteVocabQuiz(parsed) ? parsed : null;
  }, [isUser, hasContent, content]);
  const showQuizCard = quiz != null;
  const showQuizButtons =
    showQuizCard && isLastAssistant && onQuizAnswer != null;
  const showLiveClock =
    !isUser &&
    hasContent &&
    !isStreaming &&
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
      !isUser && hasContent && !isStreaming
        ? parseCalendarProposals(content)
        : [],
    [isUser, hasContent, isStreaming, content],
  );
  const showCalendarProposals = calendarProposals.length > 0 && !isStreaming;
  const places = useMemo(
    () => (!isUser && hasContent && !isStreaming ? resolvePlaces(content) : []),
    [isUser, hasContent, isStreaming, content],
  );
  const showPlaces = places.length > 0;
  const markdownContent = useMemo(() => {
    let text = showQuizCard ? stripVocabQuizBlock(content) : content;
    if (showLiveClock) text = stripTimeAnswerFences(text);
    text = stripSearchSourcesFence(text);
    if (showCalendarProposals) text = stripCalendarProposalFences(text);
    if (showPlaces) text = stripPlacesContent(text, places);
    return text;
  }, [showQuizCard, showLiveClock, showCalendarProposals, showPlaces, places, content]);
  const hasMarkdown = markdownContent.trim().length > 0;
  const showSearchSources =
    searchSources.length > 0 && !showLiveClock && !showQuizCard && !showCalendarProposals;
  const showContextSummarized =
    !isUser && !isStreaming && (message.context_summarized ?? 0) > 0;
  const collapseAssistant = shouldCollapseMessage(markdownContent);

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
          {isStreaming && !hasContent ? (
            <RecallTypingIndicator />
          ) : (
            <CollapsibleMessageBody
              enabled={!isStreaming}
              collapsible={collapseAssistant}
            >
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
                  key={message.id}
                  resetKey={`${message.id}:${markdownContent.length}`}
                  content={markdownContent}
                >
                  <MarkdownContent content={markdownContent} streaming={isStreaming} />
                  {isStreaming && hasMarkdown ? <StreamingCursor /> : null}
                </MarkdownErrorBoundary>
              ) : null}
              {showPlaces ? <PlacesListBlock places={places} /> : null}
              {showQuizCard && quiz ? (
                <VocabQuizChoices
                  quiz={quiz}
                  disabled={!showQuizButtons || !!quizDisabled}
                  language={quizLanguage}
                  initialSelected={quizSelectedLetter}
                  onSelect={
                    showQuizButtons && onQuizAnswer
                      ? (letter) => onQuizAnswer(message.id, letter)
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
          )}
        </View>
      )}

      {showActions && (
        <AssistantActions
          messageId={message.id}
          content={extractPrimaryCopyText(content)}
          feedback={message.feedback ?? null}
          onFeedback={onFeedback}
          onRegenerate={isLastAssistant ? onRegenerate : undefined}
          theme={theme}
        />
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
    userText: { color: t.userText, fontSize: 16, lineHeight: 23 },
    streamingText: { color: t.assistantText, fontSize: 16, lineHeight: 25 },
    contextChip: {
      fontSize: 12,
      lineHeight: 16,
      color: t.textTertiary,
      marginBottom: 6,
    },
  });
}
