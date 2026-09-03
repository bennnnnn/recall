import { useMemo, useState } from "react";
import { Dimensions, Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { Icon } from "@/components/Icon";
import { openAllowedUrl } from "@/lib/linkSchemePolicy";
import {
  SearchSource,
  faviconHost,
  faviconUrl,
  hostnameFromUrl,
  preferDistinctHostSources,
} from "@/lib/searchSources";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

const MAX_CHIP_ICONS = 3;

type Props = {
  sources: SearchSource[];
};

export function SearchSourcesStack({ sources }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [sheetOpen, setSheetOpen] = useState(false);

  if (sources.length === 0) return null;

  const ordered = preferDistinctHostSources(sources);
  const preview = ordered.slice(0, MAX_CHIP_ICONS);
  const label = t("chat.sources_count", { count: sources.length });

  return (
    <>
      <Pressable
        style={s.chip}
        onPress={() => setSheetOpen(true)}
        accessibilityRole="button"
        accessibilityLabel={label}
      >
        <Text style={s.chipLabel}>{label}</Text>
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
        sources={ordered}
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
  const s = useMemo(() => makeSheetStyles(theme), [theme]);
  const listMaxHeight = Math.round(Dimensions.get("window").height * 0.55);

  return (
    <AppSheet visible={visible} onClose={onClose} minBottomPadding={16} contentContainerStyle={s.sheet}>
      <Text style={s.title}>Sources</Text>
      <ScrollView
        style={[s.list, { maxHeight: listMaxHeight }]}
        bounces={false}
        showsVerticalScrollIndicator={false}
      >
        {sources.map((source, index) => (
          <SourceRow
            key={`${source.url}-${index}`}
            source={source}
            theme={theme}
            isLast={index === sources.length - 1}
          />
        ))}
      </ScrollView>
    </AppSheet>
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
    void openAllowedUrl(source.url);
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
      <Icon name="open-outline" size={16} color={theme.textSecondary} />
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
    sheet: {
      paddingTop: 4,
    },
    list: {
      paddingHorizontal: 12,
    },
    title: {
      ...Type.navTitle,
      color: theme.text,
      paddingHorizontal: 20,
      marginBottom: 8,
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
