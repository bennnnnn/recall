import { useRef, useState } from "react";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { ProjectPosGroupItems } from "@/components/ProjectPosGroupSection";
import { C } from "@/constants/Colors";
import type { ProjectItem, ProjectPosGroupSummary } from "@/lib/api";
import { partOfSpeechLabel } from "@/lib/languageLevels";

type Props = {
  token: string;
  projectId: string;
  groups: ProjectPosGroupSummary[];
  itemsByPos?: Map<string, ProjectItem[]>;
};

function groupLabel(group: ProjectPosGroupSummary): string {
  return `${partOfSpeechLabel(group.part_of_speech)}s`;
}

function groupMeta(group: ProjectPosGroupSummary): string {
  return `${group.count} words · ${group.mastered_count} mastered`;
}

export function ProjectPosGroupList({ token, projectId, groups, itemsByPos }: Props) {
  const { t } = useTranslation();
  const warnedSpeech = useRef(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const onSpeechUnavailable = () => {
    if (warnedSpeech.current) return;
    warnedSpeech.current = true;
    Alert.alert(
      "Pronunciation unavailable",
      "Rebuild the dev app so native audio works:\ncd apps/mobile && pnpm expo run:ios",
    );
  };

  if (groups.length === 0) return null;

  return (
    <View style={s.wrap}>
      <Text style={s.label}>{t("projects.word_lists")}</Text>
      {groups.map((group) => {
        const open =
          expanded[group.part_of_speech] ??
          (group.new_count > 0 && group.mastered_count === 0);
        return (
          <View key={group.part_of_speech} style={s.topicCard}>
            <Pressable
              style={s.topicHeader}
              onPress={() =>
                setExpanded((prev) => ({
                  ...prev,
                  [group.part_of_speech]: !open,
                }))
              }
            >
              <View style={s.topicHeaderMain}>
                <Text style={s.topicTitle}>{groupLabel(group)}</Text>
                <Text style={s.topicMeta}>{groupMeta(group)}</Text>
              </View>
              <Ionicons
                name={open ? "chevron-up" : "chevron-down"}
                size={18}
                color={C.textTertiary}
              />
            </Pressable>
            {open ? (
              <View style={s.topicBody}>
                <ProjectPosGroupItems
                  token={token}
                  projectId={projectId}
                  group={group}
                  initialItems={itemsByPos?.get(group.part_of_speech)}
                  onSpeechUnavailable={onSpeechUnavailable}
                />
              </View>
            ) : null}
          </View>
        );
      })}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { gap: 10 },
  label: {
    fontSize: 13,
    fontWeight: "700",
    color: C.textTertiary,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  topicCard: {
    backgroundColor: C.surface,
    borderRadius: 16,
    overflow: "hidden",
  },
  topicHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    padding: 14,
  },
  topicHeaderMain: { flex: 1, gap: 4 },
  topicTitle: { fontSize: 16, fontWeight: "700", color: C.text },
  topicMeta: { fontSize: 13, color: C.textSecondary },
  topicBody: { paddingHorizontal: 14, paddingBottom: 14 },
});
