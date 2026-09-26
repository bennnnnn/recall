import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Image } from "expo-image";

import { getInitials } from "@/lib/profile";
import { attachmentRequestHeaders, resolveAttachmentUri } from "@/features/attachments/model/attachmentUri";
import { Theme, useTheme } from "@/lib/theme";
import { Weight } from "@/lib/type";

/** Google profile picture when available, otherwise the user's initials. */
export function Avatar({
  name,
  uri,
  token = null,
  size = 34,
}: {
  name: string | null;
  uri?: string | null;
  token?: string | null;
  size?: number;
}) {
  const theme = useTheme();
  const styles = useMemo(() => makeStyles(theme), [theme]);
  const dim = { width: size, height: size, borderRadius: size / 2 };

  if (uri) {
    const resolvedUri = resolveAttachmentUri({ path: uri }) ?? uri;
    return (
      <Image
        testID="avatar-image"
        source={{ uri: resolvedUri, headers: attachmentRequestHeaders(resolvedUri, token) }}
        style={[dim, { backgroundColor: theme.surface }]}
        contentFit="cover"
        cachePolicy="memory-disk"
      />
    );
  }
  return (
    <View style={[dim, styles.fallback]}>
      <Text style={[styles.text, { fontSize: size * 0.4 }]}>{getInitials(name)}</Text>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    fallback: {
      backgroundColor: theme.primary,
      alignItems: "center",
      justifyContent: "center",
    },
    text: { color: theme.onPrimary, ...Weight.bold },
  });
}
