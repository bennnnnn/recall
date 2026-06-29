import React, { useMemo, useState } from "react";
import * as Clipboard from "expo-clipboard";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { CalendarProposalCard } from "@/components/CalendarProposalCard";
import { UserMessageContent } from "@/components/UserMessageContent";
import { SearchSourcesStack } from "@/components/SearchSourcesStack";
import { CircularClockBlock } from "@/components/rich/CircularClockBlock";
import { MarkdownContent } from "@/components/MarkdownContent";
import { MarkdownErrorBoundary } from "@/components/MarkdownErrorBoundary";
import { RecallTypingIndicator } from "@/components/RecallTypingIndicator";
import { VocabQuizChoices } from "@/components/VocabQuizChoices";
import { Message } from "@/lib/api";
import {
  parseCalendarProposals,
  stripCalendarProposalFences,
} from "@/lib/calendarProposal";
import { extractPrimaryCopyText } from "@/lib/copyBlock";
import { parseVocabQuiz, stripVocabQuizBlock } from "@/lib/parseVocabQuiz";
import {
  resolveSearchSources,
  stripSearchSourcesFence,
} from "@/lib/searchSources";
import {
  assistantReplyIsTimeAnswer,
  extractClockTimezone,
  stripTimeAnswerFences,
} from "@/lib/timeQuestion";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  message: Message;
  priorUserText?: string | null;
  isGenerating?: boolean;
  isLastAssistant?: boolean;
  onRegenerate?: () => void;
  onEdit?: (message: Message) => void;
  canEdit?: boolean;
  onFeedback?: (messageId: string, feedback: "up" | "down" | null) => void;
  onQuizAnswer?: (letter: "A" | "B" | "C" | "D") => void;
  quizDisabled?: boolean;
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
    await copyText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const rate = (dir: "up" | "down") => {
    onFeedback?.(messageId, feedback === dir ? null : dir);
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
        <Pressable style={a.btn} onPress={onRegenerate} hitSlop={8}>
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
  isLastAssistant,
  onRegenerate,
  onEdit,
  canEdit,
  onFeedback,
  onQuizAnswer,
  quizDisabled,
}: Props) {
  const theme = useTheme();
  const b = useMemo(() => makeStyles(theme), [theme]);
  const isUser = message.role === "user";
  const isStreaming = isGenerating;
  const hasContent = message.content.trim().length > 0;
  const showActions = !isUser && hasContent && !isStreaming;
  const quiz = useMemo(
    () => (!isUser && hasContent && !isStreaming ? parseVocabQuiz(message.content) : null),
    [isUser, hasContent, isStreaming, message.content],
  );
  const showQuizCard = quiz != null && !isStreaming;
  const showQuizButtons =
    showQuizCard && isLastAssistant && onQuizAnswer != null;
  const showLiveClock =
    !isUser &&
    hasContent &&
    !isStreaming &&
    assistantReplyIsTimeAnswer(message.content, priorUserText ?? null);
  const clockTimezone = useMemo(
    () => extractClockTimezone(message.content),
    [message.content],
  );
  const searchSources = useMemo(
    () => resolveSearchSources(message.content, message.search_sources),
    [message.content, message.search_sources],
  );
  const calendarProposals = useMemo(
    () =>
      !isUser && hasContent && !isStreaming
        ? parseCalendarProposals(message.content)
        : [],
    [isUser, hasContent, isStreaming, message.content],
  );
  const showCalendarProposals = calendarProposals.length > 0 && !isStreaming;
  const markdownContent = useMemo(() => {
    let text = showQuizCard ? stripVocabQuizBlock(message.content) : message.content;
    if (showLiveClock) text = stripTimeAnswerFences(text);
    text = stripSearchSourcesFence(text);
    if (showCalendarProposals) text = stripCalendarProposalFences(text);
    return text;
  }, [showQuizCard, showLiveClock, showCalendarProposals, message.content]);
  const hasMarkdown = markdownContent.trim().length > 0;
  const showSearchSources =
    searchSources.length > 0 && !showLiveClock && !showQuizCard && !showCalendarProposals;

  return (
    <View style={[b.row, isUser ? b.userRow : b.assistantRow]}>
      {isUser ? (
        <View style={b.userColumn}>
          <UserMessageContent message={message} />
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
          ) : isStreaming ? (
            <>
              <Text style={b.streamingText} selectable>
                {markdownContent}
              </Text>
              {showSearchSources ? <SearchSourcesStack sources={searchSources} /> : null}
            </>
          ) : (
            <>
              {showLiveClock ? (
                <CircularClockBlock content={clockTimezone} />
              ) : null}
              {hasMarkdown ? (
                <MarkdownErrorBoundary
                  key={message.id}
                  resetKey={`${message.id}:${markdownContent.length}`}
                  content={markdownContent}
                >
                  <MarkdownContent content={markdownContent} streaming={isGenerating} />
                </MarkdownErrorBoundary>
              ) : null}
              {showQuizCard ? (
                <VocabQuizChoices
                  quiz={quiz}
                  disabled={!showQuizButtons || !!quizDisabled}
                  onSelect={showQuizButtons ? onQuizAnswer : undefined}
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
            </>
          )}
        </View>
      )}

      {showActions && (
        <AssistantActions
          messageId={message.id}
          content={extractPrimaryCopyText(message.content)}
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
    userRow: { alignItems: "flex-end" },
    userColumn: { alignItems: "flex-end", maxWidth: "88%" },
    editBtn: { marginTop: 2, marginRight: 4, padding: 4 },
    assistantRow: { alignItems: "stretch" },
    assistantBubble: {
      maxWidth: "100%",
      backgroundColor: "transparent",
      paddingVertical: 2,
    },
    userText: { color: t.userText, fontSize: 16, lineHeight: 23 },
    streamingText: { color: t.assistantText, fontSize: 16, lineHeight: 25 },
  });
}
