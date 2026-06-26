import * as Clipboard from "expo-clipboard";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useState } from "react";

import { MarkdownContent } from "@/components/MarkdownContent";
import { MarkdownErrorBoundary } from "@/components/MarkdownErrorBoundary";
import { MessageMetaChips } from "@/components/MessageMetaChips";
import { RecallTypingIndicator } from "@/components/RecallTypingIndicator";
import { Message } from "@/lib/api";
import { extractPrimaryCopyText } from "@/lib/copyBlock";

import { C } from "@/constants/Colors";

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
}: {
  messageId: string;
  content: string;
  feedback: "up" | "down" | null;
  onFeedback?: (messageId: string, feedback: "up" | "down" | null) => void;
  onRegenerate?: () => void;
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
          size={20}
          color={copied ? C.primary : C.textSecondary}
        />
      </Pressable>
      <Pressable style={a.btn} onPress={() => rate("up")} hitSlop={8}>
        <Ionicons
          name={feedback === "up" ? "thumbs-up" : "thumbs-up-outline"}
          size={20}
          color={feedback === "up" ? C.primary : C.textSecondary}
        />
      </Pressable>
      <Pressable style={a.btn} onPress={() => rate("down")} hitSlop={8}>
        <Ionicons
          name={feedback === "down" ? "thumbs-down" : "thumbs-down-outline"}
          size={20}
          color={feedback === "down" ? C.primary : C.textSecondary}
        />
      </Pressable>
      {onRegenerate && (
        <Pressable style={a.btn} onPress={onRegenerate} hitSlop={8}>
          <Ionicons name="refresh-outline" size={20} color={C.textSecondary} />
        </Pressable>
      )}
    </View>
  );
}

export function MessageBubble({
  message,
  isGenerating = false,
  isLastAssistant,
  onRegenerate,
  onFeedback,
}: Props) {
  const isUser = message.role === "user";
  const isStreaming = isGenerating;
  const hasContent = message.content.trim().length > 0;
  const showActions = !isUser && hasContent && !isStreaming;

  return (
    <View style={[b.row, isUser ? b.userRow : b.assistantRow]}>
      <View style={[b.bubble, isUser ? b.userBubble : b.assistantBubble]}>
        {isUser ? (
          <Text style={b.userText} selectable>
            {message.content}
          </Text>
        ) : isStreaming && !hasContent ? (
          <RecallTypingIndicator />
        ) : (
          <>
            <MarkdownErrorBoundary
              key={message.id}
              resetKey={`${message.id}:${message.content.length}`}
              content={message.content}
            >
              <MarkdownContent content={message.content} />
            </MarkdownErrorBoundary>
            {!isStreaming ? <MessageMetaChips model={message.model} /> : null}
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
        />
      )}
    </View>
  );
}

const a = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    marginTop: 6,
    paddingHorizontal: 2,
  },
  btn: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
});

const b = StyleSheet.create({
  row: { marginVertical: 2, paddingHorizontal: 16 },
  userRow: { alignItems: "flex-end" },
  assistantRow: { alignItems: "stretch" },
  bubble: { borderRadius: 18, paddingHorizontal: 14, paddingVertical: 10 },
  userBubble: {
    maxWidth: "82%",
    backgroundColor: C.userBubble,
    borderBottomRightRadius: 4,
  },
  assistantBubble: {
    maxWidth: "100%",
    backgroundColor: C.bg,
    paddingHorizontal: 0,
    paddingVertical: 8,
  },
  userText: { color: C.userText, fontSize: 16, lineHeight: 22 },
});
