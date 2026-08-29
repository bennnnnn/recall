import { useMemo } from "react";
import { StyleSheet, Text } from "react-native";
import { useTranslation } from "react-i18next";

import { CardShell } from "@/components/rich/CardShell";
import { type IoniconName } from "@/lib/icons";
import { SocialPlatform } from "@/lib/richBlocks";
import { Theme, useTheme } from "@/lib/theme";

type Props = { text: string; platform: SocialPlatform };

function platformMeta(
  t: (key: string) => string,
): Record<SocialPlatform, { label: string; icon: IoniconName }> {
  return {
    twitter: { label: t("rich.post_draft_x"), icon: "logo-twitter" },
    linkedin: { label: t("rich.post_draft_linkedin"), icon: "logo-linkedin" },
    generic: { label: t("rich.social_post_draft"), icon: "megaphone-outline" },
  };
}

export function SocialPostCard({ text, platform }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const meta = platformMeta(t)[platform];

  return (
    <CardShell label={meta.label} copyText={text} icon={meta.icon} accent={false}>
      <Text style={s.body} selectable>
        {text}
      </Text>
    </CardShell>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    body: { color: t.text, fontSize: 16, lineHeight: 24 },
  });
}
