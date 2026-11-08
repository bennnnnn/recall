import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { Icon } from "@/ui/icons/Icon";
import { galleryFileParts } from "@/features/attachments/model/gallery";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { DYNAMIC_TYPE_MAX, Type } from "@/lib/type";
import { IconSize } from "@/ui/icons/sizes";

type Props = {
  /** What the item is called on screen (`galleryDisplayName`). */
  name: string;
  contentType: string;
  /** Square edge in px. */
  size: number;
  /** The grid writes the name on the tile; a column row has it beside, as its title. */
  showName?: boolean;
};

/**
 * A Library file that has no picture: a document icon, its type as a badge, and in the grid
 * its name. The name read in capitals and was cut mid-word ("CELL-BI…TES.PDF"); it now keeps
 * its own case over two lines, and the badge says what the file is however the name is cut.
 */
export function GalleryFileTile({ name, contentType, size, showName = false }: Props) {
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const { stem, type } = galleryFileParts(name, contentType);

  return (
    <View style={[s.tile, { width: size, height: size }]} testID="gallery-file-tile">
      <Icon name="file-text" size={showName ? IconSize.lg : IconSize.md} color={C.primary} />
      {type ? (
        <View style={s.badge}>
          <Text style={s.badgeText} numberOfLines={1} maxFontSizeMultiplier={DYNAMIC_TYPE_MAX}>
            {type}
          </Text>
        </View>
      ) : null}
      {showName ? (
        // A fixed square: past this scale two lines and the badge no longer fit in it.
        <Text style={s.name} numberOfLines={2} maxFontSizeMultiplier={DYNAMIC_TYPE_MAX}>
          {stem}
        </Text>
      ) : null}
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    tile: {
      borderRadius: Radius.sm,
      backgroundColor: C.surfaceAlt,
      borderWidth: 1,
      borderColor: C.border,
      alignItems: "center",
      justifyContent: "center",
      gap: Space.xxs,
      paddingHorizontal: Space.xs,
      overflow: "hidden",
    },
    badge: {
      borderRadius: Radius.xs,
      paddingHorizontal: Space.xxs + 2,
      paddingVertical: 1,
      backgroundColor: C.primary,
    },
    badgeText: {
      ...Type.micro,
      color: C.onPrimary,
    },
    name: {
      ...Type.caption,
      color: C.textSecondary,
      textAlign: "center",
    },
  });
}
