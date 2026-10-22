import React, { Suspense, useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import { CollapsibleMessageBody } from "@/components/CollapsibleMessageBody";
import { ChatMessageImage } from "@/features/attachments/components/ChatMessageImage";
import { MarkdownContent } from "@/components/MarkdownContent";
import { LinkPreviewTrust } from "@/components/markdown/LinkPreviewTrust";
import { MathDraftPreview } from "@/features/chat/components/MathDraftPreview";
import { sentMessageShowsMathPreview } from "@/lib/math/draftText";
import { useAttachmentIndexed } from "@/features/attachments/hooks/useAttachmentIndexed";
import { Message } from "@/lib/api";
import {
  fileLabelFromContentType,
  guessFileNameFromCaption,
  isPdfContentType,
  parseUserMessageContent,
} from "@/lib/messageAttachments";
import { messageListKey } from "@/lib/messageListLayout";
import { shouldCollapseMessage } from "@/lib/markdown/messageFold";
import { displayMathToInline } from "@/lib/math/solutionBars";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { IconSize } from "@/ui/icons/sizes";

// Async-split pdf.js (~1.4MB) off the chat cold path — same pattern as
// LazyHeavyRich / HtmlPreviewModal. Only a PDF attachment evaluates the vendor.
const ChatMessagePdfLazy = React.lazy(() =>
  import("@/features/attachments/components/ChatMessagePdf").then((m) => ({ default: m.ChatMessagePdf })),
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
  // A reopened message links only the file; its name comes from the server's attachment row.
  const { fileName: pdfUploadName } = useAttachmentIndexed(pdfFile?.attachmentId);
  const pdfFileName =
    message.local_file_name ??
    pdfUploadName ??
    guessFileNameFromCaption(parsed.caption, "document.pdf");
  const nonPdfFile = parsed.files.find((file) => !isPdfContentType(file.contentType));
  const {
    indexed: fileIndexed,
    failed: fileIndexFailed,
    fileName: fileUploadName,
  } = useAttachmentIndexed(nonPdfFile?.attachmentId);
  const nonPdfFileLabel =
    message.local_file_name ??
    fileUploadName ??
    fileLabelFromContentType(nonPdfFile?.contentType, t("chat.attached_file"));
  const nonPdfFileStatus = fileIndexFailed
    ? t("chat.file_index_failed")
    : fileIndexed
      ? nonPdfFileLabel
      : t("chat.file_indexing");
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
          previewFit="contain"
        />
      ))}
      {!parsed.images.length && message.local_image_uri ? (
        <ChatMessageImage localUri={message.local_image_uri} animatedReveal={false} previewFit="contain" />
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
                accessibilityLabel={nonPdfFileStatus}
              >
                <Icon name="file" size={IconSize.xs} color={C.primary} />
                <Text style={s.fileChipText} numberOfLines={1}>
                  {nonPdfFileStatus}
                </Text>
              </View>
            ) : null}
            {showCaption ? (
              <UserBubbleBody key={messageListKey(message)} content={parsed.caption} />
            ) : plainText ? (
              <UserBubbleBody key={messageListKey(message)} content={plainText} />
            ) : null}
          </View>
        </CollapsibleMessageBody>
      ) : null}
    </View>
  );
}

/** Keyed by its message: a list row reused for another message draws it afresh. */
function UserBubbleBody({ content }: { content: string }) {
  const inline = displayMathToInline(content);
  if (sentMessageShowsMathPreview(inline)) {
    return <MathDraftPreview input={inline} showCaret={false} sent />;
  }
  // The user's own links may show a preview card.
  return (
    <LinkPreviewTrust userText={content}>
      <MarkdownContent content={inline} compact />
    </LinkPreviewTrust>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    // The row caps the width (MessageBubble userColumn): capping here too made
    // a sent message 82% of 88%, about 72% of the screen.
    column: {
      maxWidth: "100%",
      alignItems: "flex-end",
      gap: Space.xs,
    },
    textBubble: {
      backgroundColor: C.userBubble,
      borderRadius: Radius.bubble,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xs,
    },
    textBubbleBelowImage: {
      alignSelf: "flex-end",
    },
    fileChip: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      paddingHorizontal: 2,
      paddingVertical: 2,
    },
    fileChipText: {
      ...Type.secondary,
      ...Weight.medium,
      color: C.textSecondary,
    },
  });
}
