/**
 * Landing scenes drawn as a chat: a picture drawn from a sentence, and a question about the
 * news answered with its sources.
 */
import { useMemo } from "react";
import { Image, StyleSheet } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { ReplyLine, Reveal, SceneCard, SceneText, UserBubble } from "./SceneParts";

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
        <SceneText style={s.sourcesText}>{t("onboarding.demo_news_sources")}</SceneText>
      </Reveal>
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
  });
}
