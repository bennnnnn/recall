import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { GalleryThumbnail } from "@/components/GalleryThumbnail";
import { Icon } from "@/components/Icon";
import { type AttachmentListItem } from "@/lib/api";
import { COLUMN_THUMB_SIZE, isGalleryImage } from "@/lib/gallery";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  item: AttachmentListItem;
  fileName: string;
  onPress: () => void;
  onLongPress: () => void;
  onMissing: (attachmentId: string) => void;
};

export function GalleryColumnRow({
  item,
  fileName,
  onPress,
  onLongPress,
  onMissing,
}: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const isImage = isGalleryImage(item.content_type);
  const chatTitle = item.chat_title?.trim() || null;

  return (
    <Pressable
      onPress={onPress}
      onLongPress={onLongPress}
      accessibilityRole="button"
      accessibilityLabel={
        isImage ? t("chat.image_view_a11y") : t("gallery.file_actions_a11y")
      }
      style={({ pressed }) => [s.row, pressed && s.rowPressed]}
    >
      {isImage ? (
        <GalleryThumbnail
          attachmentId={item.id}
          downloadUrl={item.download_url}
          size={COLUMN_THUMB_SIZE}
          onMissing={onMissing}
        />
      ) : (
        <View style={s.fileThumb}>
          <Icon name="document-outline" size={28} color={C.textTertiary} />
        </View>
      )}
      <View style={s.meta}>
        <Text style={s.fileName} numberOfLines={1}>
          {fileName}
        </Text>
        {chatTitle ? (
          <Text style={s.chatTitle} numberOfLines={1}>
            {chatTitle}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      minHeight: Space.minTouch,
      paddingVertical: Space.xs,
    },
    rowPressed: {
      backgroundColor: C.surfaceAlt,
    },
    fileThumb: {
      width: COLUMN_THUMB_SIZE,
      height: COLUMN_THUMB_SIZE,
      borderRadius: 10,
      backgroundColor: C.surfaceAlt,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      alignItems: "center",
      justifyContent: "center",
    },
    meta: {
      flex: 1,
      minWidth: 0,
    },
    fileName: {
      ...Type.body,
      color: C.text,
    },
    chatTitle: {
      ...Type.meta,
      color: C.textSecondary,
      marginTop: 2,
    },
  });
}
