import { useMemo } from "react";
import { StyleSheet } from "react-native";
import { useTranslation } from "react-i18next";

import { CardShell } from "@/components/rich/CardShell";
import { RichBodyText } from "@/components/rich/RichBodyText";
import { CalloutKind } from "@/lib/richBlocks";
import { Theme, useTheme } from "@/lib/theme";

function calloutMeta(
  theme: Theme,
  t: (key: string) => string,
): Record<
  CalloutKind,
  {
    label: string;
    color: string;
    icon:
      | "bulb-outline"
      | "information-circle-outline"
      | "warning-outline"
      | "alert-circle-outline";
  }
> {
  return {
    tip: { label: t("rich.callout_tip"), color: theme.success, icon: "bulb-outline" },
    note: { label: t("rich.callout_note"), color: theme.primary, icon: "information-circle-outline" },
    info: { label: t("rich.callout_info"), color: theme.primary, icon: "information-circle-outline" },
    warning: { label: t("rich.callout_warning"), color: theme.warning, icon: "warning-outline" },
    important: {
      label: t("rich.callout_important"),
      color: theme.danger,
      icon: "alert-circle-outline",
    },
  };
}

type Props = { kind: CalloutKind; content: string };

export function CalloutBlock({ kind, content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const meta = calloutMeta(theme, t)[kind] ?? calloutMeta(theme, t).note;
  const lines = content.split("\n");
  const firstLine = lines[0]?.trim() || "";
  const hasBody = lines.length > 1 && lines.slice(1).join("\n").trim();
  const title = hasBody ? firstLine : meta.label;
  const body = hasBody || firstLine;

  return (
    <CardShell
      label={title}
      icon={meta.icon}
      accentColor={meta.color}
      iconColor={meta.color}
    >
      <RichBodyText style={s.body} selectable>
        {body}
      </RichBodyText>
    </CardShell>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    body: { fontSize: 16, lineHeight: 24, color: t.text },
  });
}
