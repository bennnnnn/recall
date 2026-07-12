import { useMemo } from "react";
import { StyleSheet } from "react-native";

import { CardShell } from "@/components/rich/CardShell";
import { RichBodyText } from "@/components/rich/RichBodyText";
import { CalloutKind } from "@/lib/richBlocks";
import { Theme, useTheme } from "@/lib/theme";

function calloutMeta(
  t: Theme,
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
    tip: { label: "Tip", color: t.success, icon: "bulb-outline" },
    note: { label: "Note", color: t.primary, icon: "information-circle-outline" },
    info: { label: "Info", color: t.accent, icon: "information-circle-outline" },
    warning: { label: "Warning", color: t.warning, icon: "warning-outline" },
    important: {
      label: "Important",
      color: t.danger,
      icon: "alert-circle-outline",
    },
  };
}

type Props = { kind: CalloutKind; content: string };

export function CalloutBlock({ kind, content }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const meta = calloutMeta(theme)[kind] ?? calloutMeta(theme).note;
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
