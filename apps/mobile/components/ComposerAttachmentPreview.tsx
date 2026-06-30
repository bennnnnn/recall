import { ActivityIndicator, Image, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { Theme, useTheme } from "@/lib/theme";
import type { PendingAttachment } from "@/lib/attachments";

type Props = {
  attachment: PendingAttachment;
  uploading?: boolean;
  onRemove: () => void;
};

export function ComposerAttachmentPreview({ attachment, uploading, onRemove }: Props) {
  const C = useTheme();
  const s = makeStyles(C);

  if (attachment.kind === "image") {
    return (
      <View style={s.imageWrap}>
        <Image source={{ uri: attachment.localUri }} style={s.image} resizeMode="cover" />
        {uploading ? (
          <View style={s.uploadOverlay}>
            <ActivityIndicator color="#fff" />
          </View>
        ) : null}
        <Pressable
          style={s.removeBtn}
          onPress={onRemove}
          hitSlop={8}
          accessibilityLabel="Remove attachment"
          disabled={uploading}
        >
          <Ionicons name="close" size={14} color={C.text} />
        </Pressable>
      </View>
    );
  }

  return (
    <View style={s.fileWrap}>
      <View style={s.fileIcon}>
        <Ionicons name="document-outline" size={18} color={C.primary} />
      </View>
      <Text style={s.fileName} numberOfLines={1}>
        {attachment.fileName}
      </Text>
      {uploading ? (
        <ActivityIndicator size="small" color={C.primary} />
      ) : (
        <Pressable onPress={onRemove} hitSlop={8} accessibilityLabel="Remove attachment">
          <Ionicons name="close-circle" size={18} color={C.textTertiary} />
        </Pressable>
      )}
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    imageWrap: {
      width: 88,
      height: 112,
      borderRadius: 18,
      overflow: "hidden",
      marginBottom: 8,
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
      backgroundColor: "rgba(0,0,0,0.35)",
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
      gap: 8,
      marginBottom: 8,
      paddingHorizontal: 10,
      paddingVertical: 8,
      borderRadius: 12,
      backgroundColor: C.surfaceAlt,
    },
    fileIcon: {
      width: 32,
      height: 32,
      borderRadius: 8,
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
