import React, { Suspense, useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { CollapsibleMessageBody } from "@/components/CollapsibleMessageBody";
import { ChatMessageImage } from "@/components/ChatMessageImage";
import { MarkdownContent } from "@/components/MarkdownContent";
import {
  sentMessageShowsMathPreview,
  MathDraftPreview,
} from "@/components/chat/MathDraftPreview";
import { useAttachmentIndexed } from "@/hooks/useAttachmentIndexed";
import { Message } from "@/lib/api";
import {
  fileLabelFromContentType,
  guessFileNameFromCaption,
  isPdfContentType,
  parseUserMessageContent,
} from "@/lib/messageAttachments";
import { shouldCollapseMessage } from "@/lib/markdown/messageFold";
import { Radius } from "@/lib/radius";
import { Theme, useTheme } from "@/lib/theme";

// Async-split pdf.js (~1.4MB) off the chat cold path — same pattern as
// LazyHeavyRich / HtmlPreviewModal. Only a PDF attachment evaluates the vendor.
const ChatMessagePdfLazy = React.lazy(() =>
  import("@/components/ChatMessagePdf").then((m) => ({ default: m.ChatMessagePdf })),
);

type Props = {
  message: Message;
};

export function UserMessageContent({ message }: Props) {
  const C = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(C), [C]);
  const parsed = useMemo(() => parseUserMessageContent(message.content), [message.content]);
  const hasImages = parsed.images.length > 0 || Boolean(message.local_image_uri);
  const pdfFile = parsed.files.find((file) => isPdfContentType(file.contentType));
  const localPdf =
    message.local_file_uri &&
    isPdfContentType(message.local_file_content_type ?? "application/pdf");
  const showPdf = Boolean(pdfFile || localPdf);
  const pdfFileName =
    message.local_file_name ??
    guessFileNameFromCaption(parsed.caption, "document.pdf");
  const nonPdfFile = parsed.files.find((file) => !isPdfContentType(file.contentType));
  const nonPdfFileLabel =
    message.local_file_name ??
    fileLabelFromContentType(nonPdfFile?.contentType, t("chat.attached_file"));
  const fileIndexed = useAttachmentIndexed(nonPdfFile?.attachmentId);
  const showCaption =
    parsed.caption.length > 0 &&
    !(showPdf && (parsed.caption === pdfFileName || parsed.caption.endsWith(".pdf")));
  const plainText =
    !hasImages && !showPdf && !parsed.hasFileAttachment ? message.content.trim() : "";
  const showTextBubble =
    showCaption || (parsed.hasFileAttachment && !showPdf) || plainText.length > 0;
  const collapseText = shouldCollapseMessage(showCaption ? parsed.caption : plainText);

  return (
    <View style={s.column}>
      {parsed.images.map((image, index) => (
        <ChatMessageImage
          key={`${image.attachmentId ?? image.path}-${index}`}
          attachmentId={image.attachmentId}
          path={image.path}
          localUri={index === 0 ? message.local_image_uri : null}
          animatedReveal={false}
        />
      ))}
      {!parsed.images.length && message.local_image_uri ? (
        <ChatMessageImage localUri={message.local_image_uri} animatedReveal={false} />
      ) : null}

      {showPdf ? (
        <Suspense fallback={null}>
          <ChatMessagePdfLazy
            attachmentId={pdfFile?.attachmentId}
            path={pdfFile?.path}
            localUri={message.local_file_uri}
            fileName={pdfFileName}
          />
        </Suspense>
      ) : null}

      {showTextBubble ? (
        <CollapsibleMessageBody collapsible={collapseText} fadeColor={C.userBubble}>
          <View style={[s.textBubble, hasImages && s.textBubbleBelowImage]}>
            {parsed.hasFileAttachment && !showPdf ? (
              <View
                style={s.fileChip}
                accessibilityLabel={
                  fileIndexed ? nonPdfFileLabel : t("chat.file_indexing")
                }
              >
                <Icon name="document-outline" size={16} color={C.primary} />
                <Text style={s.fileChipText} numberOfLines={1}>
                  {fileIndexed ? nonPdfFileLabel : t("chat.file_indexing")}
                </Text>
              </View>
            ) : null}
            {showCaption ? (
              <UserBubbleBody content={parsed.caption} />
            ) : plainText ? (
              <UserBubbleBody content={plainText} />
            ) : null}
          </View>
        </CollapsibleMessageBody>
      ) : null}
    </View>
  );
}

function UserBubbleBody({ content }: { content: string }) {
  if (sentMessageShowsMathPreview(content)) {
    return <MathDraftPreview input={content} showCaret={false} />;
  }
  return <MarkdownContent content={content} />;
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    column: {
      maxWidth: "82%",
      alignItems: "flex-end",
      gap: 8,
    },
    textBubble: {
      backgroundColor: C.userBubble,
      borderRadius: Radius.bubble,
      paddingHorizontal: 14,
      paddingVertical: 8,
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
