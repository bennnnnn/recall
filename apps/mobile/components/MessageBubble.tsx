import React, { useMemo, useState } from "react";
import * as Clipboard from "expo-clipboard";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { MarkdownErrorBoundary } from "@/components/MarkdownErrorBoundary";
import { MessageMetaChips } from "@/components/MessageMetaChips";
import { RecallTypingIndicator } from "@/components/RecallTypingIndicator";
import { Message } from "@/lib/api";
import { extractPrimaryCopyText } from "@/lib/copyBlock";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  message: Message;
  isGenerating?: boolean;
  isLastAssistant?: boolean;
  onRegenerate?: () => void;
  onFeedback?: (messageId: string, feedback: "up" | "down" | null) => void;
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
  isGenerating = false,
  isLastAssistant,
  onRegenerate,
  onFeedback,
}: Props) {
  const theme = useTheme();
  const b = useMemo(() => makeStyles(theme), [theme]);
  const isUser = message.role === "user";
  const isStreaming = isGenerating;
  const hasContent = message.content.trim().length > 0;
  const showActions = !isUser && hasContent && !isStreaming;

  return (
    <View style={[b.row, isUser ? b.userRow : b.assistantRow]}>
      <View style={isUser ? b.userBubble : b.assistantBubble}>
        {isUser ? (
          <Text style={b.userText} selectable>
            {message.content}
          </Text>
        ) : isStreaming && !hasContent ? (
          <RecallTypingIndicator />
        ) : isStreaming ? (
          // Plain text while streaming — avoids O(n²) markdown re-parsing
          // and prevents formatting flicker (half-typed fences, tables, math).
          <Text style={b.streamingText} selectable>
            {message.content}
          </Text>
        ) : (
          <>
            <MarkdownErrorBoundary
              key={message.id}
              resetKey={`${message.id}:${message.content.length}`}
              content={message.content}
            >
              <MarkdownContent content={message.content} />
            </MarkdownErrorBoundary>
            <MessageMetaChips model={message.model} />
          </>
        )}
      </View>

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
    assistantRow: { alignItems: "stretch" },
    userBubble: {
      maxWidth: "82%",
      backgroundColor: t.userBubble,
      borderRadius: 22,
      paddingHorizontal: 16,
      paddingVertical: 10,
    },
    assistantBubble: {
      maxWidth: "100%",
      backgroundColor: "transparent",
      paddingVertical: 2,
    },
    userText: { color: t.userText, fontSize: 16, lineHeight: 23 },
    streamingText: { color: t.assistantText, fontSize: 16, lineHeight: 25 },
  });
}
