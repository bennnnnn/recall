import { memo, useMemo, useState } from "react";
import { ActivityIndicator, Image, StyleSheet, View } from "react-native";

import { Icon } from "@/components/Icon";
import { useAuthToken } from "@/contexts/AuthContext";
import { getApiUrl } from "@/lib/config";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  /** Attachment id — used to build the authenticated /file URL. */
  attachmentId: string;
  /** Optional already-resolved URL (presigned). Falls back to /file. */
  downloadUrl?: string | null;
  /** Square thumbnail size in px. */
  size?: number;
};

function GalleryThumbnailBase({ attachmentId, downloadUrl, size = 1 }: Props) {
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const token = useAuthToken();
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);

  // downloadUrl may be a relative "/attachments/{id}/file" (local backend) or
  // an absolute presigned R2 URL. Relative paths need the API base + auth.
  const isRelative = Boolean(downloadUrl && downloadUrl.startsWith("/"));
  const uri = downloadUrl
    ? isRelative
      ? `${getApiUrl()}${downloadUrl}`
      : downloadUrl
    : `${getApiUrl()}/attachments/${attachmentId}/file`;

  const source =
    token && isRelative
      ? { uri, headers: { Authorization: `Bearer ${token}` } }
      : { uri };

  const dimension = { width: size, height: size };

  return (
    <View style={[s.wrap, dimension]}>
      {failed ? (
        <View style={[s.fallback, dimension]}>
          <Icon name="image-outline" size={24} color={C.textTertiary} />
        </View>
      ) : (
        <>
          {!loaded ? (
            <View style={[s.loading, dimension]}>
              <ActivityIndicator size="small" color={C.textTertiary} />
            </View>
          ) : null}
          <Image
            source={source}
            style={dimension}
            resizeMode="cover"
            onLoad={() => setLoaded(true)}
            onError={() => setFailed(true)}
          />
        </>
      )}
    </View>
  );
}

export const GalleryThumbnail = memo(GalleryThumbnailBase);

function makeStyles(C: Theme) {
  return StyleSheet.create({
    wrap: {
      borderRadius: 10,
      overflow: "hidden",
      backgroundColor: C.surface,
    },
    loading: {
      position: "absolute",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 1,
    },
    fallback: {
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.surface,
    },
  });
}
