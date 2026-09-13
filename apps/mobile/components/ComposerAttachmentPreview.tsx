import { useMemo, useState } from "react";
import { ActivityIndicator, Image, type ImageLoadEvent, Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import type { PendingAttachment } from "@/lib/attachments";
import { fitAttachmentImage, type ImageSize } from "@/lib/attachmentImageSize";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  attachment: PendingAttachment;
  uploading?: boolean;
  onRemove: () => void;
};

export function ComposerAttachmentPreview({ attachment, uploading, onRemove }: Props) {
  const C = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(C), [C]);

  if (attachment.kind === "image") {
    return <ComposerImagePreview key={attachment.localUri} {...{ attachment, uploading, onRemove }} />;
  }

  return (
    <View
      style={s.fileWrap}
      accessibilityLabel={uploading ? t("chat.sending") : undefined}
      accessibilityState={{ busy: Boolean(uploading) }}
    >
      <View style={s.fileIcon}>
        <Icon name="document-outline" size={18} color={C.primary} />
      </View>
      <Text style={s.fileName} numberOfLines={1}>
        {attachment.fileName}
      </Text>
      {uploading ? (
        <ActivityIndicator size="small" color={C.primary} />
      ) : (
        <Pressable
          onPress={onRemove}
          hitSlop={12}
          accessibilityRole="button"
          accessibilityLabel={t("chat.remove_attachment_a11y")}
        >
          <Icon name="close-circle" size={18} color={C.textTertiary} />
        </Pressable>
      )}
    </View>
  );
}

function ComposerImagePreview({ attachment, uploading, onRemove }: Props) {
  const C = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(C), [C]);
  const bounds = { width: 88, height: 112 };
  const [decodedSize, setDecodedSize] = useState<ImageSize | null>(null);
  const size = (decodedSize && fitAttachmentImage(decodedSize, bounds)) || bounds;
  const onLoad = (event: ImageLoadEvent) => {
    const loaded = event.nativeEvent.source;
    if (fitAttachmentImage(loaded, bounds)) {
      setDecodedSize({ width: loaded.width, height: loaded.height });
    }
  };
  return (
    <View
      style={[s.imageControls, { width: Math.max(size.width, 44), height: Math.max(size.height, 44) }]}
      accessibilityLabel={uploading ? t("chat.sending") : undefined}
      accessibilityState={{ busy: Boolean(uploading) }}
      testID="composer-image-controls"
    >
      <View style={[s.imageWrap, size]} testID="composer-image-frame">
        <Image
          source={{ uri: attachment.localUri }}
          style={s.image}
          resizeMode="contain"
          onLoad={onLoad}
          testID="composer-image-preview"
        />
        {uploading ? (
          <View style={s.uploadOverlay}>
            <ActivityIndicator color={C.onPrimary} />
          </View>
        ) : null}
      </View>
      <Pressable
        style={s.removeBtn}
        onPress={onRemove}
        hitSlop={12}
        accessibilityRole="button"
        accessibilityLabel={t("chat.remove_attachment_a11y")}
        disabled={uploading}
      >
        <Icon name="close" size={14} color={C.text} />
      </Pressable>
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    imageControls: {
      marginBottom: Space.xs,
    },
    imageWrap: {
      borderRadius: Radius.bubble,
      overflow: "hidden",
      backgroundColor: C.surfaceAlt,
    },
    image: {
      width: "100%",
      height: "100%",
    },
    uploadOverlay: {
      ...StyleSheet.absoluteFill,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.scrim,
    },
    removeBtn: {
      position: "absolute",
      top: 4,
      right: 4,
      width: 22,
      height: 22,
      borderRadius: 11,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.bg,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
    },
    fileWrap: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      marginBottom: Space.xs,
      paddingHorizontal: 10,
      paddingVertical: Space.xs,
      borderRadius: Radius.md,
      backgroundColor: C.surfaceAlt,
    },
    fileIcon: {
      width: 32,
      height: 32,
      borderRadius: Radius.xs,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.primaryLight,
    },
    fileName: {
      flex: 1,
      fontSize: 13,
      color: C.textSecondary,
    },
  });
}
