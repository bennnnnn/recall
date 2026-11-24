/**
 * Landing scenes drawn as a chat: a picture drawn from a sentence, a question about the news
 * answered with its sources, and a reminder made from one sentence, which, as in the app,
 * waits for its tap before it is added.
 */
import { useMemo } from "react";
import { Image, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Reveal, ReplyLine, SceneCard, UserBubble } from "./SceneParts";

type SceneProps = { active: boolean };

/** Made once with the app's own picture model, and shipped so the slide works offline. */
const FOX_PICTURE = require("@/assets/images/landing-fox.jpg");

export function ImageScene({ active }: SceneProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <SceneCard>
      <Reveal active={active} step={0}>
        <UserBubble text={t("onboarding.demo_image_ask")} />
      </Reveal>
      <Reveal active={active} step={2} style={s.pictureFrame}>
        <Image source={FOX_PICTURE} style={s.picture} resizeMode="cover" accessibilityIgnoresInvertColors />
      </Reveal>
    </SceneCard>
  );
}

const NEWS_POINTS = ["onboarding.demo_news_1", "onboarding.demo_news_2", "onboarding.demo_news_3"];

export function NewsScene({ active }: SceneProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <SceneCard>
      <Reveal active={active} step={0}>
        <UserBubble text={t("onboarding.demo_news_ask")} />
      </Reveal>
      {NEWS_POINTS.map((key, index) => (
        <Reveal key={key} active={active} step={index + 1}>
          <ReplyLine text={`• ${t(key)}`} />
        </Reveal>
      ))}
      <Reveal active={active} step={NEWS_POINTS.length + 1} style={s.sources}>
        <Icon name="link" size={IconSize.xs} color={theme.textSecondary} />
        <Text style={s.sourcesText}>{t("onboarding.demo_news_sources")}</Text>
      </Reveal>
    </SceneCard>
  );
}

export function ReminderScene({ active }: SceneProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <SceneCard>
      <Reveal active={active} step={0}>
        <UserBubble text={t("onboarding.demo_remind_ask")} />
      </Reveal>
      <Reveal active={active} step={1} style={s.reminder}>
        <View style={s.reminderIcon}>
          <Icon name="bell" size={IconSize.sm} color={theme.primary} />
        </View>
        <View style={s.reminderText}>
          <Text style={s.reminderTitle}>{t("onboarding.demo_remind_title")}</Text>
          <Text style={s.reminderWhen}>{t("onboarding.demo_remind_when")}</Text>
        </View>
      </Reveal>
      <View>
        <Reveal active={active} step={2} style={s.addButton}>
          <Text style={s.addText}>{t("onboarding.demo_remind_add")}</Text>
        </Reveal>
        <View style={s.overlay} pointerEvents="none">
          <Reveal active={active} step={3} style={[s.addButton, s.added]}>
            <Icon name="check" size={IconSize.xs} color={theme.success} />
            <Text style={s.addedText}>{t("onboarding.demo_remind_added")}</Text>
          </Reveal>
        </View>
      </View>
    </SceneCard>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    // The picture fills the card's room under the ask, whatever the screen's height.
    pictureFrame: { flex: 1, alignSelf: "stretch", marginBottom: Space.md },
    picture: { width: "100%", height: "100%", borderRadius: Radius.lg },
    sources: {
      flexDirection: "row",
      alignItems: "center",
      alignSelf: "flex-start",
      gap: Space.xxs,
      borderRadius: Radius.full,
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xxs,
    },
    sourcesText: { ...Type.caption, ...Weight.semibold, color: theme.textSecondary },
    reminder: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      borderRadius: Radius.lg,
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      padding: Space.sm,
      marginTop: Space.xs,
    },
    reminderIcon: {
      width: 36,
      height: 36,
      borderRadius: Radius.md,
      backgroundColor: theme.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    reminderText: { flex: 1 },
    reminderTitle: { ...Type.body, ...Weight.semibold, color: theme.text },
    reminderWhen: { ...Type.caption, color: theme.textSecondary },
    addButton: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: Space.xxs,
      borderRadius: Radius.full,
      backgroundColor: theme.primary,
      paddingVertical: Space.sm,
    },
    addText: { ...Type.secondary, ...Weight.semibold, color: theme.onPrimary },
    // The confirmed state covers the button it replaces, as the tap in the app does.
    overlay: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0 },
    added: { flex: 1, backgroundColor: theme.successLight },
    addedText: { ...Type.secondary, ...Weight.semibold, color: theme.success },
  });
}
