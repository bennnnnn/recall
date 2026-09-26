import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as Clipboard from "expo-clipboard";
import { Icon } from "@/ui/icons/Icon";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { CalendarProposalCard } from "@/features/integrations/components/CalendarProposalCard";
import { SettingsProposalCard } from "@/components/SettingsProposalCard";
import { PlacesListBlock } from "@/components/PlacesListBlock";
import { UserMessageContent } from "@/components/UserMessageContent";
import { ChatMessageImageStrip } from "@/components/ChatMessageImageStrip";
import { ImageGenPlaceholder } from "@/features/images/components/ImageGenPlaceholder";
import { ActionShimmer } from "@/ui/feedback/ActionShimmer";
import { SearchSourcesStack } from "@/components/SearchSourcesStack";
import { LazyCircularClockBlock } from "@/components/rich/LazyHeavyRich";
import { MarkdownContent } from "@/components/MarkdownContent";
import { StreamingCursor } from "@/components/StreamingCursor";
import { MarkdownErrorBoundary } from "@/components/MarkdownErrorBoundary";
import { RecallTypingIndicator } from "@/components/RecallTypingIndicator";
import { LearningLaunchButton } from "@/features/learning/components/LearningLaunchButton";
import { AssistantMessageScope } from "@/features/integrations/context/emailDraftPersist";
import { Message } from "@/lib/api";
import { extractPrimaryCopyText } from "@/lib/copyBlock";
import { notifySuccess, notifyWarning, selection, tap } from "@/lib/haptics";
import { SENDING_LABEL_DELAY_MS } from "@/lib/chat/messageLogic";
import { useAssistantMessageContent } from "@/hooks/useAssistantMessageContent";
import { useStreamLayoutHold } from "@/hooks/useStreamLayoutHold";
import { formatAssistantMathExpr } from "@/lib/math/formatInput";
import { parseUserMessageContent } from "@/lib/messageAttachments";
import { shouldShowWaitingIndicator, useRotatingStreamStatus } from "@/lib/streamStatusLabel";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { speakPlainText, stopSpeaking } from "@/features/speech/model/pronunciation";
import { speechLocale } from "@/lib/i18n/languages";
import { useAuth, useAuthToken } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useTranslation } from "react-i18next";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { IconSize } from "@/ui/icons/sizes";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";

type Props = {
  message: Message;
  priorUserText?: string | null;
  isGenerating?: boolean;
  /** Live token stream — avoids mutating the messages array on every token. */
  liveContent?: string;
  liveSearchSources?: Message["search_sources"];
  streamStatus?: string;
  streamStatusDetail?: string;
  isLastAssistant?: boolean;
  onRegenerate?: () => void;
  regenerating?: boolean;
  onFeedback?: (messageId: string, feedback: "up" | "down" | null) => void;
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

function useCopyFeedback() {
  const [copied, setCopied] = useState(false);
  const resetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showCopied = useCallback(() => {
    if (resetTimerRef.current) clearTimeout(resetTimerRef.current);
    setCopied(true);
    resetTimerRef.current = setTimeout(() => {
      resetTimerRef.current = null;
      setCopied(false);
    }, 1500);
  }, []);

  useEffect(
    () => () => {
      if (resetTimerRef.current) clearTimeout(resetTimerRef.current);
    },
    [],
  );

  return { copied, showCopied };
}

function UserActions({
  content,
  theme,
}: {
  content: string;
  theme: Theme;
}) {
  const { t } = useTranslation();
  const { copied, showCopied } = useCopyFeedback();

  const handleCopy = async () => {
    if (!content.trim()) return;
    await copyText(content);
    showCopied();
    notifySuccess();
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
          name={copied ? "check" : "copy"}
          size={IconSize.sm}
          color={copied ? theme.primary : theme.textSecondary}
        />
        </Pressable>
    </View>
  );
}

function AssistantActions({
  messageId,
  markdown,
  feedback,
  onFeedback,
  onRegenerate,
  regenerating = false,
  theme,
  hidden = false,
  thumbsOnly = false,
}: {
  messageId: string;
  markdown: string;
  feedback: "up" | "down" | null;
  onFeedback?: (messageId: string, feedback: "up" | "down" | null) => void;
  onRegenerate?: () => void;
  regenerating?: boolean;
  theme: Theme;
  hidden?: boolean;
  /** Image-only replies: thumbs only (no copy / speak / regenerate). */
  thumbsOnly?: boolean;
}) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const token = useAuthToken();
  const feedbackApi = useActionFeedbackOptional();
  const { copied, showCopied } = useCopyFeedback();
  const [speaking, setSpeaking] = useState(false);
  const speakGenRef = useRef(0);
  const copyPayload = extractPrimaryCopyText(markdown);

  const handleCopy = async () => {
    if (!copyPayload.trim()) return;
    await copyText(copyPayload);
    showCopied();
    notifySuccess();
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
    const result = await speakPlainText(markdown, speechLocale(user?.locale), {
      token,
      preferCloud: true,
    });
    if (gen !== speakGenRef.current) return;
    setSpeaking(false);
    if (!result.ok) {
      reportRecoverableError(
        feedbackApi,
        result.reason === "unavailable"
          ? t("chat.read_aloud_unavailable_body")
          : t("chat.read_aloud_failed_body"),
      );
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
            disabled={!copyPayload.trim()}
            accessibilityRole="button"
            accessibilityLabel={t("common.copy")}
          >
            <Icon
              name={copied ? "check" : "copy"}
              size={IconSize.sm}
              color={copied ? theme.primary : theme.textSecondary}
            />
          </Pressable>
          <Pressable
            style={a.btn}
            onPress={() => void handleSpeak()}
            hitSlop={8}
            disabled={!markdown.trim()}
            accessibilityRole="button"
            accessibilityLabel={t("chat.read_aloud_a11y")}
          >
            <Icon
              name="volume"
              filled={speaking}
              size={IconSize.sm}
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
          name="thumbs-up"
          filled={feedback === "up"}
          size={IconSize.sm}
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
          name="thumbs-down"
          filled={feedback === "down"}
          size={IconSize.sm}
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
            <Icon name="refresh" size={IconSize.sm} color={theme.textSecondary} />
          )}
        </Pressable>
      ) : null}
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
  streamStatusDetail,
  isLastAssistant,
  onRegenerate,
  regenerating = false,
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
  const isUser = message.role === "user";
  const holdStreamLayout = useStreamLayoutHold({
    isGenerating,
    isUser,
    renderKey: message.renderKey,
  });
  const isStreaming = isGenerating;
  const layoutFrozen = isStreaming || holdStreamLayout;

  const userCopyText = isUser ? userMessageCopyText(message.content) : "";
  const canRevealUserActions = isUser && userCopyText.length > 0;

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
  }, [message.id]);

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
    hasContent,
    showActionSlot,
    actionsReady,
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
    learningLaunch,
  } = assistant;

  const imageGenFailure = message.image_gen_failure;
  const showWaitingIndicator = shouldShowWaitingIndicator({ isStreaming, hasContent });
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
    !showLiveClock &&
    !showCalendarProposals &&
    !showSettingsProposals &&
    !showPlaces;

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
              theme={theme}
            />
          ) : null}
        </View>
      ) : (
        <View style={b.assistantBubble}>
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
            {showImages ? <ChatMessageImageStrip images={images} /> : null}
            {showLiveClock ? (
              <LazyCircularClockBlock content={clockTimezone} />
            ) : null}
            {hasMarkdown ? (
              <AssistantMessageScope messageId={message.id}>
                <MarkdownErrorBoundary
                  resetKey={markdownResetKey}
                  content={markdownContent}
                >
                  <MarkdownContent
                    content={markdownContent}
                    streaming={markdownStreamMode}
                    mathFormat={formatAssistantMathExpr}
                  />
                  {isStreaming && hasMarkdown ? <StreamingCursor /> : null}
                </MarkdownErrorBoundary>
              </AssistantMessageScope>
            ) : null}
            {message.generationStopped ? (
              <Text style={b.stoppedFooter}>{t("chat.generation_stopped")}</Text>
            ) : null}
            {showPlaces ? <PlacesListBlock places={places} /> : null}
            {(() => {
              const launchProjectId = learningLaunch?.projectId ?? lessonProjectId ?? "";
              const showLessonCta =
                !isStreaming &&
                Boolean(onOpenLesson) &&
                Boolean(launchProjectId) &&
                learningLaunch != null;
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
        </View>
      )}

      {showActionSlot && actionsReady && !imageGenFailure ? (
        <View style={b.actionRowSlot}>
          <AssistantActions
            messageId={message.id}
            markdown={markdownContent}
            feedback={message.feedback ?? null}
            onFeedback={onFeedback}
            onRegenerate={isLastAssistant ? onRegenerate : undefined}
            regenerating={isLastAssistant && regenerating}
            theme={theme}
            thumbsOnly={imageOnlyActions}
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
    marginTop: Space.xxs,
    marginLeft: 2,
  },
  userRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "flex-end",
    gap: 2,
    marginTop: Space.xxs,
    marginRight: 2,
  },
  rowHidden: {
    opacity: 0,
  },
  btn: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
});

function makeStyles(t: Theme) {
  return StyleSheet.create({
    row: { marginVertical: 6, paddingHorizontal: Space.md },
    rowHighlighted: {
      backgroundColor: t.primaryLight,
      borderRadius: Radius.md,
      marginHorizontal: Space.xs,
      paddingHorizontal: Space.xs,
    },
    userRow: { alignItems: "flex-end" },
    userColumn: { alignItems: "flex-end", maxWidth: "88%" },
    sendingStatus: {
      marginTop: Space.xxs,
      marginRight: Space.xxs,
    },
    sendingLabel: {
      ...Type.compact,
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
      paddingVertical: Space.xxs,
    },
    imageGenWaitingWrap: {
      flexDirection: "column",
      alignItems: "flex-start",
      gap: Space.xs,
      paddingVertical: Space.xxs,
    },
    statusLabel: {
      ...Type.secondary,
      color: t.textTertiary,
    },
    stoppedFooter: {
      marginTop: Space.xs,
      ...Type.compact,
      color: t.textTertiary,
    },
    actionRowSlot: {
      minHeight: 44,
      marginTop: 2,
    },
  });
}
