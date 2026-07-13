import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { CollapsibleMessageBody } from "@/components/CollapsibleMessageBody";
import { ChatMessageImage } from "@/components/ChatMessageImage";
import { ChatMessagePdf } from "@/components/ChatMessagePdf";
import { MarkdownContent } from "@/components/MarkdownContent";
import { Message } from "@/lib/api";
import {
  guessFileNameFromCaption,
  isPdfContentType,
  parseUserMessageContent,
} from "@/lib/messageAttachments";
import { shouldCollapseMessage } from "@/lib/messageFold";
import { isVocabQuizAnswer, parseQuizAnswerLetter } from "@/lib/parseVocabQuiz";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  message: Message;
};

export function UserMessageContent({ message }: Props) {
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const parsed = useMemo(() => parseUserMessageContent(message.content), [message.content]);
  const quizLetter = useMemo(
    () => (isVocabQuizAnswer(message.content) ? parseQuizAnswerLetter(message.content) : null),
    [message.content],
  );
  const hasImages = parsed.images.length > 0 || Boolean(message.local_image_uri);
  const pdfFile = parsed.files.find((file) => isPdfContentType(file.contentType));
  const localPdf =
    message.local_file_uri &&
    isPdfContentType(message.local_file_content_type ?? "application/pdf");
  const showPdf = Boolean(pdfFile || localPdf);
  const pdfFileName =
    message.local_file_name ??
    guessFileNameFromCaption(parsed.caption, "document.pdf");
  const showCaption =
    parsed.caption.length > 0 &&
    !(showPdf && (parsed.caption === pdfFileName || parsed.caption.endsWith(".pdf")));
  const plainText =
    !hasImages && !showPdf && !parsed.hasFileAttachment ? message.content.trim() : "";
  const showTextBubble =
    !quizLetter &&
    (showCaption || (parsed.hasFileAttachment && !showPdf) || plainText.length > 0);
  const collapseText = shouldCollapseMessage(showCaption ? parsed.caption : plainText);

  return (
    <View style={s.column}>
      {parsed.images.map((image, index) => (
        <ChatMessageImage
          key={`${image.attachmentId ?? image.path}-${index}`}
          attachmentId={image.attachmentId}
          path={image.path}
          localUri={index === 0 ? message.local_image_uri : null}
        />
      ))}
      {!parsed.images.length && message.local_image_uri ? (
        <ChatMessageImage localUri={message.local_image_uri} />
      ) : null}

      {showPdf ? (
        <ChatMessagePdf
          attachmentId={pdfFile?.attachmentId}
          path={pdfFile?.path}
          localUri={message.local_file_uri}
          fileName={pdfFileName}
        />
      ) : null}

      {quizLetter ? (
        <View style={s.quizAnswer} accessibilityLabel={`Quiz answer ${quizLetter}`}>
          <Ionicons name="checkmark-circle-outline" size={16} color={C.primary} />
          <Text style={s.quizAnswerLetter}>{quizLetter}</Text>
        </View>
      ) : null}

      {showTextBubble ? (
        <CollapsibleMessageBody collapsible={collapseText} fadeColor={C.userBubble}>
          <View style={[s.textBubble, hasImages && s.textBubbleBelowImage]}>
            {parsed.hasFileAttachment && !showPdf ? (
              <View style={s.fileChip}>
                <Ionicons name="document-outline" size={16} color={C.primary} />
                <Text style={s.fileChipText} numberOfLines={1}>
                  Attached file
                </Text>
              </View>
            ) : null}
            {showCaption ? (
              <MarkdownContent content={parsed.caption} />
            ) : plainText ? (
              <MarkdownContent content={plainText} />
            ) : null}
          </View>
        </CollapsibleMessageBody>
      ) : null}
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    column: {
      maxWidth: "82%",
      alignItems: "flex-end",
      gap: 8,
    },
    quizAnswer: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      backgroundColor: C.primaryLight,
      borderRadius: 999,
      borderWidth: 1.5,
      borderColor: C.primary,
      paddingHorizontal: 12,
      paddingVertical: 6,
    },
    quizAnswerLetter: {
      color: C.primary,
      fontSize: 15,
      fontWeight: "800",
    },
    textBubble: {
      backgroundColor: C.userBubble,
      borderRadius: 22,
      paddingHorizontal: 16,
      paddingVertical: 10,
    },
    textBubbleBelowImage: {
      alignSelf: "flex-end",
    },
    fileChip: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      paddingHorizontal: 2,
      paddingVertical: 2,
    },
    fileChipText: {
      color: C.textSecondary,
      fontSize: 14,
      fontWeight: "500",
    },
  });
}
