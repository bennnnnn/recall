import { useMemo } from "react";
import { StyleSheet, Text } from "react-native";

import { CardShell } from "@/components/rich/CardShell";
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
    tip: { label: "Tip", color: "#34C759", icon: "bulb-outline" },
    note: { label: "Note", color: t.primary, icon: "information-circle-outline" },
    info: { label: "Info", color: "#007AFF", icon: "information-circle-outline" },
    warning: { label: "Warning", color: "#FF9500", icon: "warning-outline" },
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
      <Text style={s.body} selectable>
        {body}
      </Text>
    </CardShell>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    body: { fontSize: 16, lineHeight: 24, color: t.text },
  });
}
