import { useEffect, useMemo, useRef, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { ProjectPosGroupItems } from "@/components/ProjectPosGroupSection";
import { Theme, useTheme } from "@/lib/theme";
import type { ProjectPosGroupSummary } from "@/lib/api";
import { partOfSpeechLabel } from "@/lib/languageLevels";

type Props = {
  token: string;
  projectId: string;
  groups: ProjectPosGroupSummary[];
  onItemUpdated?: () => void;
};

function groupLabel(group: ProjectPosGroupSummary): string {
  return `${partOfSpeechLabel(group.part_of_speech)}s`;
}

function tabLabel(group: ProjectPosGroupSummary): string {
  return partOfSpeechLabel(group.part_of_speech);
}

function masteryPct(group: ProjectPosGroupSummary): number {
  if (group.count <= 0) return 0;
  return Math.round((group.mastered_count / group.count) * 100);
}

export function ProjectPosGroupList({ token, projectId, groups, onItemUpdated }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const warnedSpeech = useRef(false);
  const [activePos, setActivePos] = useState(groups[0]?.part_of_speech ?? "");

  useEffect(() => {
    if (groups.length === 0) return;
    if (!groups.some((g) => g.part_of_speech === activePos)) {
      setActivePos(groups[0].part_of_speech);
    }
  }, [groups, activePos]);

  const onSpeechUnavailable = () => {
    if (warnedSpeech.current) return;
    warnedSpeech.current = true;
    Alert.alert(
      "Pronunciation unavailable",
      "Rebuild the dev app so native audio works:\ncd apps/mobile && pnpm expo run:ios",
    );
  };

  if (groups.length === 0) return null;

  const totalWords = groups.reduce((sum, g) => sum + g.count, 0);
  const activeGroup = groups.find((g) => g.part_of_speech === activePos) ?? groups[0];
  const pct = masteryPct(activeGroup);

  return (
    <View style={s.wrap}>
      <View style={s.header}>
        <Text style={s.label}>{t("projects.word_lists")}</Text>
        <Text style={s.totalBadge}>{t("projects.word_lists_total", { count: totalWords })}</Text>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={s.tabs}
        style={s.tabsScroll}
      >
        {groups.map((group) => {
          const active = group.part_of_speech === activeGroup.part_of_speech;
          return (
            <Pressable
              key={group.part_of_speech}
              style={[s.tab, active && s.tabActive]}
              onPress={() => setActivePos(group.part_of_speech)}
              accessibilityRole="tab"
              accessibilityState={{ selected: active }}
            >
              <Text style={[s.tabText, active && s.tabTextActive]}>{tabLabel(group)}</Text>
              <View style={[s.tabBadge, active && s.tabBadgeActive]}>
                <Text style={[s.tabBadgeText, active && s.tabBadgeTextActive]}>
                  {group.count}
                </Text>
              </View>
            </Pressable>
          );
        })}
      </ScrollView>

      <View style={s.panel}>
        <View style={s.panelHeader}>
          <View style={s.panelHeaderMain}>
            <Text style={s.panelTitle}>{groupLabel(activeGroup)}</Text>
            <Text style={s.panelMeta}>
              {t("projects.word_list_count", { count: activeGroup.count })}
              {pct > 0 ? ` · ${pct}% ${t("projects.status_mastered").toLowerCase()}` : ""}
            </Text>
          </View>
        </View>
        <View style={s.track}>
          <View style={[s.fill, { width: `${pct}%` }]} />
        </View>
        <View style={s.statsRow}>
          {activeGroup.new_count > 0 ? (
            <StatChip label={t("projects.status_new")} value={activeGroup.new_count} muted />
          ) : null}
          {activeGroup.learning_count > 0 ? (
            <StatChip
              label={t("projects.status_learning")}
              value={activeGroup.learning_count}
              accent={theme.warning}
            />
          ) : null}
          {activeGroup.mastered_count > 0 ? (
            <StatChip
              label={t("projects.status_mastered")}
              value={activeGroup.mastered_count}
              accent={theme.primary}
            />
          ) : null}
        </View>
        <View style={s.panelBody}>
          <ProjectPosGroupItems
            key={activeGroup.part_of_speech}
            token={token}
            projectId={projectId}
            group={activeGroup}
            onSpeechUnavailable={onSpeechUnavailable}
            onItemUpdated={onItemUpdated}
          />
        </View>
      </View>
    </View>
  );
}

function StatChip({
  label,
  value,
  accent,
  muted = false,
}: {
  label: string;
  value: number;
  accent?: string;
  muted?: boolean;
}) {
  const theme = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
      <View
        style={{
          width: 6,
          height: 6,
          borderRadius: 3,
          backgroundColor: muted ? theme.textTertiary : (accent ?? theme.textTertiary),
        }}
      />
      <Text style={{ fontSize: 12, fontWeight: "600", color: theme.textSecondary }}>
        {value} {label.toLowerCase()}
      </Text>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: { gap: 10 },
    header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
    label: {
      fontSize: 13,
      fontWeight: "700",
      color: theme.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
    },
    totalBadge: {
      fontSize: 12,
      fontWeight: "700",
      color: theme.primary,
      backgroundColor: theme.primaryLight,
      paddingHorizontal: 10,
      paddingVertical: 4,
      borderRadius: 999,
    },
    tabsScroll: { marginHorizontal: -2 },
    tabs: { flexDirection: "row", gap: 8, paddingHorizontal: 2, paddingBottom: 2 },
    tab: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      paddingHorizontal: 14,
      paddingVertical: 10,
      borderRadius: 999,
      backgroundColor: theme.surface,
      borderWidth: 1,
      borderColor: theme.border,
    },
    tabActive: {
      backgroundColor: theme.primaryLight,
      borderColor: theme.primary,
    },
    tabText: { fontSize: 14, fontWeight: "700", color: theme.textSecondary },
    tabTextActive: { color: theme.primaryDark },
    tabBadge: {
      minWidth: 22,
      height: 22,
      borderRadius: 11,
      paddingHorizontal: 6,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: theme.bg,
    },
    tabBadgeActive: { backgroundColor: theme.primary },
    tabBadgeText: { fontSize: 12, fontWeight: "800", color: theme.textSecondary },
    tabBadgeTextActive: { color: theme.onPrimary },
    panel: {
      backgroundColor: theme.surface,
      borderRadius: 16,
      padding: 14,
      gap: 10,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    panelHeader: { flexDirection: "row", alignItems: "flex-start" },
    panelHeaderMain: { flex: 1, gap: 2 },
    panelTitle: { fontSize: 17, fontWeight: "700", color: theme.text },
    panelMeta: { fontSize: 13, color: theme.textSecondary },
    track: {
      height: 4,
      borderRadius: 2,
      backgroundColor: theme.border,
      overflow: "hidden",
    },
    fill: { height: 4, borderRadius: 2, backgroundColor: theme.primary },
    statsRow: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 10 },
    panelBody: {
      paddingTop: 4,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: theme.border,
    },
  });
}
