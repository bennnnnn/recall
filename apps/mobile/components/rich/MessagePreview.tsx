import { useMemo } from "react";
import { StyleSheet, Text } from "react-native";
import { useTranslation } from "react-i18next";

import { CopyButton } from "@/components/CopyButton";
import { CardShell } from "@/components/rich/CardShell";
import { Theme, useTheme } from "@/lib/theme";

type Props = { text: string; label?: string };

export function MessagePreview({ text, label }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const resolvedLabel = label ?? t("rich.message_draft");

  return (
    <CardShell
      label={resolvedLabel}
      icon="chatbubble-outline"
      accent={false}
      headerActions={<CopyButton text={text} variant="icon" />}
    >
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
