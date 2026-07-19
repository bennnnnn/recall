import React, { useEffect, useMemo, useState } from "react";
import * as Clipboard from "expo-clipboard";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View, Alert } from "react-native";

import { CalendarProposalCard } from "@/components/CalendarProposalCard";
import { PlacesListBlock } from "@/components/PlacesListBlock";
import { CollapsibleMessageBody } from "@/components/CollapsibleMessageBody";
import { UserMessageContent } from "@/components/UserMessageContent";
import { ChatMessageImage } from "@/components/ChatMessageImage";
import { ImageGenPlaceholder } from "@/components/ImageGenPlaceholder";
import { SearchSourcesStack } from "@/components/SearchSourcesStack";
import { CircularClockBlock } from "@/components/rich/CircularClockBlock";
import { MarkdownContent } from "@/components/MarkdownContent";
import { StreamingCursor } from "@/components/StreamingCursor";
import { MarkdownErrorBoundary } from "@/components/MarkdownErrorBoundary";
import { RecallTypingIndicator } from "@/components/RecallTypingIndicator";
import { ReasoningBlock } from "@/components/chat/ReasoningBlock";
import { VocabCard } from "@/components/VocabCard";
import { VocabQuizChoices } from "@/components/VocabQuizChoices";
import { Message } from "@/lib/api";
import { extractPrimaryCopyText } from "@/lib/copyBlock";
import { exportMessageAsPdf } from "@/lib/exportMessagePdf";
import { isShareCancelled } from "@/lib/exportPdf";
import { notifySuccess, notifyWarning, selection, tap } from "@/lib/haptics";
import { SENDING_LABEL_DELAY_MS } from "@/lib/chatMessageLogic";
import { useAssistantMessageContent } from "@/hooks/useAssistantMessageContent";
import { useStreamLayoutHold } from "@/hooks/useStreamLayoutHold";
import { parseUserMessageContent } from "@/lib/messageAttachments";
import { shouldShowWaitingIndicator, useRotatingStreamStatus } from "@/lib/streamStatusLabel";
import { Theme, useTheme } from "@/lib/theme";
import { speakPlainText, stopSpeaking } from "@/lib/pronunciation";
import { useAuthToken } from "@/contexts/AuthContext";
import { useTranslation } from "react-i18next";

type Props = {
  message: Message;
  priorUserText?: string | null;
  isGenerating?: boolean;
  /** Live token stream — avoids mutating the messages array on every token. */
  liveContent?: string;
  liveSearchSources?: Message["search_sources"];
  liveReasoning?: string;
  streamStatus?: string;
  streamStatusDetail?: string;
  isLastAssistant?: boolean;
  onRegenerate?: () => void;
  onEdit?: (message: Message) => void;
  canEdit?: boolean;
  onFeedback?: (messageId: string, feedback: "up" | "down" | null) => void;
  quizLanguage?: string;
  highlighted?: boolean;
  isSending?: boolean;
  onQuizAnswer?: (letter: string) => void;
};

async function copyText(text: string) {
  await Clipboard.setStringAsync(text);
}

function userMessageCopyText(content: string): string {
  const caption = parseUserMessageContent(content).caption.trim();
  return caption || content.trim();
}

function UserActions({
  content,
  onEdit,
  theme,
}: {
  content: string;
  onEdit?: () => void;
  theme: Theme;
}) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!content.trim()) return;
    tap();
    await copyText(content);
    setCopied(true);
    notifySuccess();
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <View style={a.userRow}>
      <Pressable
        style={a.btn}
        onPress={() => void handleCopy()}
        hitSlop={8}
        disabled={!content.trim()}
        accessibilityRole="button"
        accessibilityLabel={t("common.copy")}
      >
        <Ionicons
          name={copied ? "checkmark-outline" : "copy-outline"}
          size={19}
          color={copied ? theme.primary : theme.textSecondary}
        />
      </Pressable>
      {onEdit ? (
        <Pressable
          style={a.btn}
          onPress={() => {
            tap();
            onEdit();
          }}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel={t("chat.edit_message_a11y")}
        >
          <Ionicons name="pencil-outline" size={19} color={theme.textSecondary} />
        </Pressable>
      ) : null}
    </View>
  );
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
  const { t } = useTranslation();
  const token = useAuthToken();
  const [copied, setCopied] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [exporting, setExporting] = useState(false);

  const handleCopy = async () => {
    tap();
    await copyText(content);
    setCopied(true);
    notifySuccess();
    setTimeout(() => setCopied(false), 1500);
  };

  const handleSpeak = async () => {
    if (speaking) {
      stopSpeaking();
      setSpeaking(false);
      return;
    }
    tap();
    setSpeaking(true);
    const result = await speakPlainText(content, "en-US", { token });
    setSpeaking(false);
    if (!result.ok) {
      Alert.alert(t("chat.read_aloud_unavailable_title"), t("chat.read_aloud_unavailable_body"));
    }
  };

  const handleExportPdf = async () => {
    if (exporting || !content.trim()) return;
    tap();
    setExporting(true);
    try {
      const titleMatch = content.match(/^#\s+(.+)$/m);
      const title = titleMatch?.[1]?.trim() || t("chat.export_pdf_default_title");
      await exportMessageAsPdf(title, content);
    } catch (error) {
      if (isShareCancelled(error)) return;
      Alert.alert(t("common.error"), t("chat.export_pdf_failed"));
    } finally {
      setExporting(false);
    }
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
        accessibilityRole="button"
        accessibilityLabel={t("common.copy")}
      >
        <Ionicons
          name={copied ? "checkmark-outline" : "copy-outline"}
          size={19}
          color={copied ? theme.primary : theme.textSecondary}
        />
      </Pressable>
      <Pressable
        style={a.btn}
        onPress={() => void handleSpeak()}
        hitSlop={8}
        disabled={!content.trim()}
        accessibilityRole="button"
        accessibilityLabel={t("chat.read_aloud_a11y")}
      >
        <Ionicons
          name={speaking ? "volume-high" : "volume-high-outline"}
          size={19}
          color={speaking ? theme.primary : theme.textSecondary}
        />
      </Pressable>
      <Pressable
        style={a.btn}
        onPress={() => void handleExportPdf()}
        hitSlop={8}
        disabled={!content.trim() || exporting}
        accessibilityRole="button"
        accessibilityLabel={t("chat.export_pdf_a11y")}
      >
        <Ionicons
          name={exporting ? "hourglass-outline" : "document-text-outline"}
          size={19}
          color={theme.textSecondary}
        />
      </Pressable>
      <Pressable
        style={a.btn}
        onPress={() => rate("up")}
        hitSlop={8}
        accessibilityRole="button"
        accessibilityLabel={t("chat.thumbs_up_a11y")}
      >
        <Ionicons
          name={feedback === "up" ? "thumbs-up" : "thumbs-up-outline"}
          size={19}
          color={feedback === "up" ? theme.primary : theme.textSecondary}
        />
      </Pressable>
      <Pressable
        style={a.btn}
        onPress={() => rate("down")}
        hitSlop={8}
        accessibilityRole="button"
        accessibilityLabel={t("chat.thumbs_down_a11y")}
      >
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
          accessibilityRole="button"
          accessibilityLabel={t("chat.regenerate_a11y")}
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
  liveReasoning,
  streamStatus,
  streamStatusDetail,
  isLastAssistant,
  onRegenerate,
  onEdit,
  canEdit,
  onFeedback,
  quizLanguage = "en",
  highlighted = false,
  isSending = false,
  onQuizAnswer,
}: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const b = useMemo(() => makeStyles(theme), [theme]);
  const [showSendingLabel, setShowSendingLabel] = useState(false);
  const [showUserActions, setShowUserActions] = useState(false);
  const isUser = message.role === "user";
  const holdStreamLayout = useStreamLayoutHold({
    isGenerating,
    isUser,
    renderKey: message.renderKey,
  });
  const isStreaming = isGenerating;
  const layoutFrozen = isStreaming || holdStreamLayout;
  const userCopyText = isUser ? userMessageCopyText(message.content) : "";
  const canShowEdit = Boolean(canEdit && onEdit && !message.id.startsWith("local-"));
  const canRevealUserActions = isUser && (userCopyText.length > 0 || canShowEdit);

  useEffect(() => {
    if (!isSending) {
      setShowSendingLabel(false);
      return;
    }
    const timer = setTimeout(() => setShowSendingLabel(true), SENDING_LABEL_DELAY_MS);
    return () => clearTimeout(timer);
  }, [isSending]);

  useEffect(() => {
    setShowUserActions(false);
  }, [message.id, canShowEdit]);

  const assistant = useAssistantMessageContent({
    message,
    liveContent,
    liveSearchSources,
    priorUserText,
    layoutFrozen,
    isGenerating,
    isUser,
  });
  const {
    content,
    hasContent,
    showActionSlot,
    actionsReady,
    showVocabCard,
    vocabCard,
    showLiveClock,
    clockTimezone,
    calendarProposals,
    showCalendarProposals,
    places,
    showPlaces,
    images,
    showImages,
    markdownContent,
    hasMarkdown,
    showSearchSources,
    searchSources,
    markdownStreamMode,
    markdownResetKey,
    interactiveQuiz,
  } = assistant;

  const reasoningText =
    liveReasoning?.trim() ||
    (holdStreamLayout ? message.reasoning_preview?.trim() : "") ||
    "";
  const showReasoning = !isUser && reasoningText.length > 0;
  const showWaitingIndicator = shouldShowWaitingIndicator({ isStreaming, hasContent, showReasoning });
  const statusLabel = useRotatingStreamStatus(
    streamStatus,
    showWaitingIndicator,
    t,
    streamStatusDetail,
  );

  return (
    <View style={[b.row, isUser ? b.userRow : b.assistantRow, highlighted && b.rowHighlighted]}>
      {isUser ? (
        <View style={b.userColumn}>
          <Pressable
            onLongPress={() => {
              if (!canRevealUserActions) return;
              selection();
              setShowUserActions(true);
            }}
            onPress={() => {
              if (showUserActions) setShowUserActions(false);
            }}
            delayLongPress={350}
            accessibilityHint={
              canRevealUserActions ? t("chat.user_message_actions_hint") : undefined
            }
          >
            <UserMessageContent message={message} />
          </Pressable>
          {showSendingLabel ? (
            <Text style={b.sendingLabel}>{t("chat.sending")}</Text>
          ) : null}
          {showUserActions ? (
            <UserActions
              content={userCopyText}
              onEdit={
                canShowEdit
                  ? () => {
                      setShowUserActions(false);
                      onEdit?.(message);
                    }
                  : undefined
              }
              theme={theme}
            />
          ) : null}
        </View>
      ) : (
        <View style={b.assistantBubble}>
          {showReasoning ? (
            <ReasoningBlock content={reasoningText} streaming={isStreaming} />
          ) : null}
          <CollapsibleMessageBody
            enabled={!layoutFrozen && hasContent}
            collapsible={false}
          >
            {showWaitingIndicator ? (
              streamStatus === "image_gen" ? (
                <View style={b.imageGenWaitingWrap}>
                  <ImageGenPlaceholder statusText={statusLabel} />
                </View>
              ) : (
                <View style={b.waitingWrap}>
                  <RecallTypingIndicator />
                  {statusLabel ? <Text style={b.statusLabel}>{statusLabel}</Text> : null}
                </View>
              )
            ) : null}
            {showImages
              ? images.map((image, index) => (
                  <ChatMessageImage
                    key={`${image.attachmentId ?? image.path}-${index}`}
                    attachmentId={image.attachmentId}
                    path={image.path}
                  />
                ))
              : null}
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
            {showVocabCard && vocabCard ? (
              <VocabCard card={vocabCard} language={quizLanguage} />
            ) : null}
            {interactiveQuiz && !isStreaming ? (
              <VocabQuizChoices
                choices={interactiveQuiz.choices}
                disabled={!onQuizAnswer || Boolean(isGenerating)}
                onSelect={(letter) => onQuizAnswer?.(letter)}
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

      {showActionSlot ? (
        <View style={b.actionRowSlot}>
          <AssistantActions
            messageId={message.id}
            content={extractPrimaryCopyText(content)}
            feedback={message.feedback ?? null}
            onFeedback={onFeedback}
            onRegenerate={isLastAssistant ? onRegenerate : undefined}
            theme={theme}
            hidden={!actionsReady}
          />
        </View>
      ) : null}
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
  userRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "flex-end",
    gap: 2,
    marginTop: 4,
    marginRight: 2,
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
    imageGenWaitingWrap: {
      flexDirection: "column",
      alignItems: "flex-start",
      gap: 8,
      paddingVertical: 4,
    },
    statusLabel: {
      fontSize: 14,
      color: t.textTertiary,
    },
    actionRowSlot: {
      minHeight: 38,
      marginTop: 2,
    },
  });
}
