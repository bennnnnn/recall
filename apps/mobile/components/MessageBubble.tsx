import React, { useEffect, useMemo, useRef, useState } from "react";
import * as Clipboard from "expo-clipboard";
import { Icon } from "@/components/Icon";
import { ActivityIndicator, Pressable, StyleSheet, Text, View, Alert } from "react-native";

import { CalendarProposalCard } from "@/components/CalendarProposalCard";
import { SettingsProposalCard } from "@/components/SettingsProposalCard";
import { PlacesListBlock } from "@/components/PlacesListBlock";
import { CollapsibleMessageBody } from "@/components/CollapsibleMessageBody";
import { UserMessageContent } from "@/components/UserMessageContent";
import { ChatMessageImage } from "@/components/ChatMessageImage";
import { ImageGenPlaceholder } from "@/components/ImageGenPlaceholder";
import { ActionShimmer } from "@/components/ActionShimmer";
import { SearchSourcesStack } from "@/components/SearchSourcesStack";
import { CircularClockBlock } from "@/components/rich/CircularClockBlock";
import { MarkdownContent } from "@/components/MarkdownContent";
import { StreamingCursor } from "@/components/StreamingCursor";
import { MarkdownErrorBoundary } from "@/components/MarkdownErrorBoundary";
import { RecallTypingIndicator } from "@/components/RecallTypingIndicator";
import { ReasoningBlock } from "@/components/chat/ReasoningBlock";
import { LearningLaunchButton } from "@/components/LearningLaunchButton";
import { Message } from "@/lib/api";
import { extractPrimaryCopyText } from "@/lib/copyBlock";
import { notifySuccess, notifyWarning, selection, tap } from "@/lib/haptics";
import { SENDING_LABEL_DELAY_MS } from "@/lib/chatMessageLogic";
import { useAssistantMessageContent } from "@/hooks/useAssistantMessageContent";
import { useStreamLayoutHold } from "@/hooks/useStreamLayoutHold";
import { parseUserMessageContent } from "@/lib/messageAttachments";
import { shouldShowWaitingIndicator, useRotatingStreamStatus } from "@/lib/streamStatusLabel";
import { Theme, useTheme } from "@/lib/theme";
import { prefetchReadAloud, speakPlainText, stopSpeaking } from "@/lib/pronunciation";
import { useAuthToken } from "@/contexts/AuthContext";
import { useTranslation } from "react-i18next";

type Props = {
  message: Message;
  priorUserText?: string | null;
  /** User row: this letter is answering an in-progress A–D quiz. */
  isQuizReply?: boolean;
  isGenerating?: boolean;
  /** Live token stream — avoids mutating the messages array on every token. */
  liveContent?: string;
  liveSearchSources?: Message["search_sources"];
  liveReasoning?: string;
  streamStatus?: string;
  streamStatusDetail?: string;
  isLastAssistant?: boolean;
  onRegenerate?: () => void;
  regenerating?: boolean;
  onEdit?: (message: Message) => void;
  canEdit?: boolean;
  onFeedback?: (messageId: string, feedback: "up" | "down" | null) => void;
  quizLanguage?: string;
  highlighted?: boolean;
  isSending?: boolean;
  lessonProjectId?: string | null;
  onOpenLesson?: (projectId: string) => void;
  onRetryImageGen?: () => void;
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
        <Icon
          name={copied ? "checkmark-outline" : "copy-outline"}
          size={20}
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
          <Icon name="pencil-outline" size={20} color={theme.textSecondary} />
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
  regenerating = false,
  theme,
  hidden = false,
  thumbsOnly = false,
  prefetchSpeech = false,
}: {
  messageId: string;
  content: string;
  feedback: "up" | "down" | null;
  onFeedback?: (messageId: string, feedback: "up" | "down" | null) => void;
  onRegenerate?: () => void;
  regenerating?: boolean;
  theme: Theme;
  hidden?: boolean;
  /** Image-only replies: thumbs only (no copy / speak / regenerate). */
  thumbsOnly?: boolean;
  /** Latest finished assistant reply — warm the first cloud TTS clip. */
  prefetchSpeech?: boolean;
}) {
  const { t } = useTranslation();
  const token = useAuthToken();
  const [copied, setCopied] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const speakGenRef = useRef(0);

  useEffect(() => {
    if (!prefetchSpeech || thumbsOnly || hidden || !token || !content.trim()) return;
    void prefetchReadAloud(content, token);
  }, [prefetchSpeech, thumbsOnly, hidden, token, content]);

  const handleCopy = async () => {
    tap();
    await copyText(content);
    setCopied(true);
    notifySuccess();
    setTimeout(() => setCopied(false), 1500);
  };

  const handleSpeak = async () => {
    if (speaking) {
      speakGenRef.current += 1;
      stopSpeaking();
      setSpeaking(false);
      return;
    }
    const gen = ++speakGenRef.current;
    tap();
    setSpeaking(true);
    const result = await speakPlainText(content, "en-US", { token });
    if (gen !== speakGenRef.current) return;
    setSpeaking(false);
    if (!result.ok) {
      Alert.alert(t("chat.read_aloud_unavailable_title"), t("chat.read_aloud_unavailable_body"));
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
    <View
      style={[a.row, hidden && a.rowHidden]}
      pointerEvents={hidden ? "none" : "auto"}
      accessibilityElementsHidden={hidden}
      importantForAccessibility={hidden ? "no-hide-descendants" : "auto"}
    >
      {!thumbsOnly ? (
        <>
          <Pressable
            style={a.btn}
            onPress={handleCopy}
            hitSlop={8}
            disabled={!content.trim()}
            accessibilityRole="button"
            accessibilityLabel={t("common.copy")}
          >
            <Icon
              name={copied ? "checkmark-outline" : "copy-outline"}
              size={20}
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
            <Icon
              name={speaking ? "volume-high" : "volume-high-outline"}
              size={20}
              color={speaking ? theme.primary : theme.textSecondary}
            />
          </Pressable>
        </>
      ) : null}
      <Pressable
        style={a.btn}
        onPress={() => rate("up")}
        hitSlop={8}
        accessibilityRole="button"
        accessibilityLabel={t("chat.thumbs_up_a11y")}
      >
        <Icon
          name={feedback === "up" ? "thumbs-up" : "thumbs-up-outline"}
          size={20}
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
        <Icon
          name={feedback === "down" ? "thumbs-down" : "thumbs-down-outline"}
          size={20}
          color={feedback === "down" ? theme.danger : theme.textSecondary}
        />
      </Pressable>
      {!thumbsOnly && onRegenerate ? (
        <Pressable
          style={a.btn}
          onPress={() => {
            tap();
            onRegenerate();
          }}
          disabled={regenerating}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel={t("chat.regenerate_a11y")}
          accessibilityState={{ disabled: regenerating, busy: regenerating }}
        >
          {regenerating ? (
            <ActivityIndicator size="small" color={theme.primary} />
          ) : (
            <Icon name="refresh-outline" size={20} color={theme.textSecondary} />
          )}
        </Pressable>
      ) : null}
    </View>
  );
}

export const MessageBubble = React.memo(function MessageBubble({
  message,
  priorUserText = null,
  isQuizReply = false,
  isGenerating = false,
  liveContent,
  liveSearchSources,
  liveReasoning,
  streamStatus,
  streamStatusDetail,
  isLastAssistant,
  onRegenerate,
  regenerating = false,
  onEdit,
  canEdit,
  onFeedback,
  highlighted = false,
  isSending = false,
  lessonProjectId = null,
  onOpenLesson,
  onRetryImageGen,
}: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const b = useMemo(() => makeStyles(theme), [theme]);
  const [showSendingLabel, setShowSendingLabel] = useState(false);
  const [showUserActions, setShowUserActions] = useState(false);
  const [wasStreamed, setWasStreamed] = useState(false);
  const isUser = message.role === "user";
  const holdStreamLayout = useStreamLayoutHold({
    isGenerating,
    isUser,
    renderKey: message.renderKey,
  });
  const isStreaming = isGenerating;
  const layoutFrozen = isStreaming || holdStreamLayout;

  useEffect(() => {
    if (isGenerating) setWasStreamed(true);
  }, [isGenerating]);
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
    wasStreamed,
  });
  const {
    content,
    hasContent,
    showActionSlot,
    actionsReady,
    showVocabCard,
    showLiveClock,
    clockTimezone,
    calendarProposals,
    showCalendarProposals,
    settingsProposals,
    showSettingsProposals,
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
    learningLaunch,
  } = assistant;

  const reasoningText =
    liveReasoning?.trim() ||
    (holdStreamLayout ? message.reasoning_preview?.trim() : "") ||
    "";
  const showReasoning = !isUser && reasoningText.length > 0;
  const imageGenFailure = message.image_gen_failure;
  const showWaitingIndicator = shouldShowWaitingIndicator({ isStreaming, hasContent, showReasoning });
  const statusLabel = useRotatingStreamStatus(
    streamStatus,
    showWaitingIndicator,
    t,
    streamStatusDetail,
  );
  // Generated image with no prose — copy/speak/PDF/regenerate are noise.
  const imageOnlyActions =
    showImages &&
    !hasMarkdown &&
    !showVocabCard &&
    !showLiveClock &&
    !showCalendarProposals &&
    !showSettingsProposals &&
    !showPlaces &&
    !interactiveQuiz;

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
            <UserMessageContent message={message} isQuizReply={isQuizReply} />
          </Pressable>
          {showSendingLabel ? (
            <ActionShimmer
              label={t("chat.sending")}
              compact
              color={theme.primary}
              style={b.sendingStatus}
              textStyle={b.sendingLabel}
              testID={`sending-${message.id}`}
            />
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
            {imageGenFailure ? (
              <View style={b.imageGenWaitingWrap}>
                <ImageGenPlaceholder
                  outcome={imageGenFailure}
                  statusText={
                    imageGenFailure === "canceled"
                      ? t("chat.image_gen_canceled")
                      : message.image_gen_error?.trim() || t("chat.image_gen_failed")
                  }
                  onRetry={onRetryImageGen}
                />
              </View>
            ) : showWaitingIndicator ? (
              streamStatus === "image_gen" ? (
                <View style={b.imageGenWaitingWrap}>
                  <ImageGenPlaceholder statusText={statusLabel} />
                </View>
              ) : (
                <View style={b.waitingWrap}>
                  <RecallTypingIndicator phase={streamStatus} />
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
            {(() => {
              const launchProjectId = learningLaunch?.projectId ?? lessonProjectId ?? "";
              const showLessonCta =
                !isStreaming &&
                Boolean(onOpenLesson) &&
                Boolean(launchProjectId) &&
                (learningLaunch != null ||
                  (Boolean(isLastAssistant) && Boolean(interactiveQuiz || showVocabCard)));
              return showLessonCta ? (
                <LearningLaunchButton
                  action={learningLaunch?.action}
                  onPress={() => onOpenLesson?.(launchProjectId)}
                />
              ) : null;
            })()}
            {showCalendarProposals
              ? calendarProposals.map((proposal, index) => (
                  <CalendarProposalCard
                    key={`${proposal.proposal_id ?? proposal.title}-${index}`}
                    proposal={proposal}
                    disabled={!isLastAssistant}
                  />
                ))
              : null}
            {showSettingsProposals
              ? settingsProposals.map((proposal, index) => (
                  <SettingsProposalCard
                    key={`${proposal.proposal_id}-${index}`}
                    proposal={proposal}
                    disabled={!isLastAssistant}
                  />
                ))
              : null}
            {showSearchSources ? <SearchSourcesStack sources={searchSources} /> : null}
          </CollapsibleMessageBody>
        </View>
      )}

      {showActionSlot && actionsReady && !imageGenFailure ? (
        <View style={b.actionRowSlot}>
          <AssistantActions
            messageId={message.id}
            content={extractPrimaryCopyText(content)}
            feedback={message.feedback ?? null}
            onFeedback={onFeedback}
            onRegenerate={isLastAssistant ? onRegenerate : undefined}
            regenerating={isLastAssistant && regenerating}
            theme={theme}
            thumbsOnly={imageOnlyActions}
            prefetchSpeech={Boolean(isLastAssistant && !isGenerating)}
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
    sendingStatus: {
      marginTop: 4,
      marginRight: 4,
    },
    sendingLabel: {
      fontSize: 13,
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
