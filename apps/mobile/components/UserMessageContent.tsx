import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { ChatMessageImage } from "@/components/ChatMessageImage";
import { Message } from "@/lib/api";
import { parseUserMessageContent } from "@/lib/messageAttachments";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  message: Message;
};

export function UserMessageContent({ message }: Props) {
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const parsed = useMemo(() => parseUserMessageContent(message.content), [message.content]);
  const hasImages = parsed.images.length > 0 || Boolean(message.local_image_uri);
  const showCaption = parsed.caption.length > 0;
  const plainText = !hasImages && !parsed.hasFileAttachment ? message.content.trim() : "";
  const showTextBubble = showCaption || parsed.hasFileAttachment || plainText.length > 0;

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

      {showTextBubble ? (
        <View style={[s.textBubble, hasImages && s.textBubbleBelowImage]}>
          {parsed.hasFileAttachment ? (
            <View style={s.fileChip}>
              <Ionicons name="document-outline" size={16} color={C.primary} />
              <Text style={s.fileChipText} numberOfLines={1}>
                Attached file
              </Text>
            </View>
          ) : null}
          {showCaption ? (
            <Text style={s.text} selectable>
              {parsed.caption}
            </Text>
          ) : plainText ? (
            <Text style={s.text} selectable>
              {plainText}
            </Text>
          ) : null}
        </View>
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
    textBubble: {
      backgroundColor: C.userBubble,
      borderRadius: 22,
      paddingHorizontal: 16,
      paddingVertical: 10,
    },
    textBubbleBelowImage: {
      alignSelf: "flex-end",
    },
    text: {
      color: C.userText,
      fontSize: 16,
      lineHeight: 23,
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
