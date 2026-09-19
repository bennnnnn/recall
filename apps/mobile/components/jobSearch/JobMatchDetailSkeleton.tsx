import { useMemo } from "react";
import { StyleSheet, View } from "react-native";

import { SkeletonBlock } from "@/components/SkeletonLoader";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";

export function JobMatchDetailSkeleton() {
  const theme = useTheme();
  const styles = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={styles.content} testID="job-match-detail-skeleton">
      <View style={styles.heading}>
        <SkeletonBlock width={56} height={56} borderRadius={17} />
        <View style={styles.headingCopy}>
          <SkeletonBlock width="82%" height={20} />
          <SkeletonBlock width="52%" height={15} />
        </View>
      </View>

      <View style={styles.chips}>
        <SkeletonBlock width={92} height={30} borderRadius={Radius.full} />
        <SkeletonBlock width={116} height={30} borderRadius={Radius.full} />
        <SkeletonBlock width={76} height={30} borderRadius={Radius.full} />
      </View>

      <View style={styles.copy}>
        <SkeletonBlock height={15} />
        <SkeletonBlock width="94%" height={15} />
        <SkeletonBlock width="68%" height={15} />
      </View>

      <View style={styles.card}>
        <SkeletonBlock width="38%" height={16} />
        <SkeletonBlock width="88%" height={14} />
        <SkeletonBlock width="74%" height={14} />
        <SkeletonBlock width="81%" height={14} />
      </View>

      <View style={styles.actions}>
        <SkeletonBlock width={112} height={44} borderRadius={Radius.full} />
        <SkeletonBlock width={86} height={44} borderRadius={Radius.full} />
        <SkeletonBlock width={98} height={44} borderRadius={Radius.full} />
      </View>

      <SkeletonBlock height={52} borderRadius={Radius.xl} />
      <SkeletonBlock height={132} borderRadius={Radius.xl} />
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    content: {
      flex: 1,
      padding: Space.md,
      gap: Space.md,
      backgroundColor: theme.bg,
    },
    heading: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
    },
    headingCopy: { flex: 1, gap: Space.xs },
    chips: { flexDirection: "row", flexWrap: "wrap", gap: Space.xs },
    copy: { gap: Space.xs },
    card: {
      gap: Space.sm,
      padding: Space.md,
      borderRadius: Radius.xl,
      backgroundColor: theme.contentSurface,
    },
    actions: { flexDirection: "row", flexWrap: "wrap", gap: Space.xs },
  });
}
