import { useMemo, useState } from "react";
import {
  Image,
  Linking,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  SearchSource,
  faviconHost,
  faviconUrl,
  hostnameFromUrl,
} from "@/lib/searchSources";
import { Theme, useTheme } from "@/lib/theme";

const MAX_CHIP_ICONS = 3;

type Props = {
  sources: SearchSource[];
};

export function SearchSourcesStack({ sources }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [sheetOpen, setSheetOpen] = useState(false);

  if (sources.length === 0) return null;

  const preview = sources.slice(0, MAX_CHIP_ICONS);

  return (
    <>
      <Pressable
        style={s.chip}
        onPress={() => setSheetOpen(true)}
        accessibilityRole="button"
        accessibilityLabel={`Sources, ${sources.length} links`}
      >
        <Text style={s.chipLabel}>Sources</Text>
        <View style={s.iconCluster}>
          {preview.map((source, index) => (
            <View
              key={`${source.url}-${index}`}
              style={[s.iconSlot, index > 0 && s.iconOverlap, { zIndex: MAX_CHIP_ICONS - index }]}
            >
              <FaviconCircle url={source.url} size={22} ringColor={theme.surface} />
            </View>
          ))}
        </View>
      </Pressable>

      <SearchSourcesSheet
        visible={sheetOpen}
        sources={sources}
        onClose={() => setSheetOpen(false)}
      />
    </>
  );
}

function SearchSourcesSheet({
  visible,
  sources,
  onClose,
}: {
  visible: boolean;
  sources: SearchSource[];
  onClose: () => void;
}) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const s = useMemo(() => makeSheetStyles(theme), [theme]);

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={s.root}>
        <Pressable style={s.backdrop} onPress={onClose} />
        <View style={[s.panel, { paddingBottom: Math.max(insets.bottom, 16) }]}>
          <View style={s.handle} />
          <Text style={s.title}>Sources</Text>
          <ScrollView style={s.list} bounces={false} showsVerticalScrollIndicator={false}>
            {sources.map((source, index) => (
              <SourceRow
                key={`${source.url}-${index}`}
                source={source}
                theme={theme}
                isLast={index === sources.length - 1}
              />
            ))}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

function SourceRow({
  source,
  theme,
  isLast,
}: {
  source: SearchSource;
  theme: Theme;
  isLast: boolean;
}) {
  const s = makeSheetStyles(theme);
  const domain = hostnameFromUrl(source.url);
  const open = () => {
    if (source.url) Linking.openURL(source.url).catch(() => {});
  };

  return (
    <Pressable
      style={[s.row, !isLast && s.rowBorder]}
      onPress={open}
      accessibilityRole="link"
      accessibilityLabel={source.title}
    >
      <FaviconCircle url={source.url} size={28} ringColor={theme.bg} />
      <View style={s.body}>
        <Text style={s.domain} numberOfLines={1}>
          {domain}
        </Text>
        <Text style={s.rowTitle} numberOfLines={2}>
          {source.title}
        </Text>
        {source.snippet ? (
          <Text style={s.snippet} numberOfLines={2}>
            {source.snippet}
          </Text>
        ) : null}
      </View>
      <Ionicons name="open-outline" size={16} color={theme.textSecondary} />
    </Pressable>
  );
}

function FaviconCircle({
  url,
  size,
  ringColor,
}: {
  url: string;
  size: number;
  ringColor: string;
}) {
  const theme = useTheme();
  const [failed, setFailed] = useState(false);
  const host = faviconHost(url);
  const uri = faviconUrl(url);
  const ring = Math.max(2, Math.round(size * 0.09));

  const frame = {
    width: size,
    height: size,
    borderRadius: size / 2,
    borderWidth: ring,
    borderColor: ringColor,
    overflow: "hidden" as const,
    backgroundColor: theme.surfaceAlt,
    alignItems: "center" as const,
    justifyContent: "center" as const,
  };

  if (failed || !uri) {
    return (
      <View style={frame}>
        <Text style={{ fontSize: size * 0.42, fontWeight: "800", color: theme.primary }}>
          {host.slice(0, 1).toUpperCase()}
        </Text>
      </View>
    );
  }

  return (
    <View style={frame}>
      <Image
        source={{ uri }}
        style={{ width: size - ring * 2, height: size - ring * 2 }}
        onError={() => setFailed(true)}
      />
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    chip: {
      alignSelf: "flex-start",
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      marginTop: 12,
      paddingLeft: 14,
      paddingRight: 12,
      paddingVertical: 8,
      borderRadius: 999,
      backgroundColor: theme.surface,
    },
    chipLabel: {
      fontSize: 14,
      fontWeight: "500",
      color: theme.textSecondary,
    },
    iconCluster: {
      flexDirection: "row",
      alignItems: "center",
    },
    iconSlot: {
      position: "relative",
    },
    iconOverlap: {
      marginLeft: -7,
    },
  });
}

function makeSheetStyles(theme: Theme) {
  return StyleSheet.create({
    root: {
      flex: 1,
      justifyContent: "flex-end",
    },
    backdrop: {
      ...StyleSheet.absoluteFill,
      backgroundColor: theme.scrim,
    },
    panel: {
      backgroundColor: theme.bg,
      borderTopLeftRadius: 20,
      borderTopRightRadius: 20,
      paddingTop: 8,
      maxHeight: "72%",
    },
    handle: {
      alignSelf: "center",
      width: 36,
      height: 4,
      borderRadius: 2,
      backgroundColor: theme.border,
      marginBottom: 10,
    },
    title: {
      fontSize: 17,
      fontWeight: "700",
      color: theme.text,
      paddingHorizontal: 20,
      marginBottom: 8,
    },
    list: {
      paddingHorizontal: 12,
    },
    row: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: 12,
      paddingHorizontal: 8,
      paddingVertical: 12,
    },
    rowBorder: {
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: theme.border,
    },
    body: {
      flex: 1,
      gap: 2,
    },
    domain: {
      fontSize: 12,
      fontWeight: "600",
      color: theme.textSecondary,
    },
    rowTitle: {
      fontSize: 15,
      fontWeight: "600",
      color: theme.text,
      lineHeight: 20,
    },
    snippet: {
      fontSize: 13,
      color: theme.textSecondary,
      lineHeight: 18,
      marginTop: 2,
    },
  });
}
