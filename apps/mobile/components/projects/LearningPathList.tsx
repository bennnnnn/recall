import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import {
  branchAccess,
  domainAccess,
  type DomainProgress,
} from "@/lib/projects/domainPath";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Access = "done" | "current" | "locked";

type Props = {
  domains: DomainProgress[];
  upNext?: string | null;
  onOpenChapter: (title: string) => void;
};

const NODE = 64;

export function LearningPathList({ domains, upNext, onOpenChapter }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  if (domains.length === 0) {
    return null;
  }

  return (
    <View style={s.list}>
      {domains.map((domain) => {
        const domainState = domainAccess(domains, domain.title, upNext);
        const locked = domainState === "locked";
        return (
          <View key={domain.title} style={s.group}>
            <Text style={s.domain}>{domain.title}</Text>
            <View style={s.path}>
              {domain.chapters.map((chapter, index) => {
                const access = branchAccess(chapter, upNext, locked);
                return (
                  <View key={chapter.title} style={s.step}>
                    {index > 0 ? <View style={s.stem} /> : null}
                    <PathNode
                      title={chapter.title}
                      access={access}
                      wordsLabel={t("projects.chapter_words", {
                        done: chapter.mastered,
                        total: chapter.total,
                      })}
                      offset={index % 2 === 0 ? -Space.lg : Space.lg}
                      onPress={() => {
                        if (access === "locked") return;
                        onOpenChapter(chapter.title);
                      }}
                      styles={s}
                    />
                  </View>
                );
              })}
            </View>
          </View>
        );
      })}
    </View>
  );
}

function PathNode({
  title,
  access,
  wordsLabel,
  offset,
  onPress,
  styles: s,
}: {
  title: string;
  access: Access;
  wordsLabel: string;
  offset: number;
  onPress: () => void;
  styles: ReturnType<typeof makeStyles>;
}) {
  const theme = useTheme();
  const locked = access === "locked";
  const initial = title.trim().charAt(0).toUpperCase() || "•";
  return (
    <Pressable
      style={[s.nodeWrap, { transform: [{ translateX: offset }] }]}
      onPress={onPress}
      disabled={locked}
      accessibilityRole="button"
      accessibilityState={{ disabled: locked }}
      accessibilityLabel={`${title}. ${wordsLabel}`}
    >
      <View
        style={[
          s.node,
          access === "done" ? s.nodeDone : null,
          access === "current" ? s.nodeCurrent : null,
          locked ? s.nodeLocked : null,
        ]}
      >
        {access === "done" ? (
          <Icon name="checkmark" size={28} color={theme.onPrimary} />
        ) : locked ? (
          <Icon name="lock-closed-outline" size={22} color={theme.textTertiary} />
        ) : (
          <Text style={s.initial}>{initial}</Text>
        )}
      </View>
      <Text style={[s.title, locked ? s.titleLocked : null]} numberOfLines={2}>
        {title}
      </Text>
      <Text style={s.words}>{wordsLabel}</Text>
    </Pressable>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    list: { gap: Space.xl },
    group: { gap: Space.md },
    domain: {
      ...Type.overline,
      color: theme.textTertiary,
      textAlign: "center",
    },
    path: { alignItems: "center" },
    step: { alignItems: "center" },
    stem: {
      width: 3,
      height: Space.lg,
      backgroundColor: theme.border,
      borderRadius: 2,
    },
    nodeWrap: {
      alignItems: "center",
      width: 160,
      gap: Space.xs,
    },
    node: {
      width: NODE,
      height: NODE,
      borderRadius: NODE / 2,
      alignItems: "center",
      justifyContent: "center",
    },
    nodeCurrent: { backgroundColor: theme.primary },
    nodeDone: { backgroundColor: theme.success },
    nodeLocked: {
      backgroundColor: theme.surfaceAlt,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    initial: { fontSize: 22, fontWeight: "800", color: theme.onPrimary },
    title: {
      ...Type.label,
      color: theme.text,
      textAlign: "center",
    },
    titleLocked: { color: theme.textTertiary },
    words: { ...Type.caption, color: theme.textSecondary, textAlign: "center" },
  });
}
