import { StyleSheet, Text } from "react-native";

import { CardShell } from "@/components/rich/CardShell";
import { CalloutKind } from "@/lib/richBlocks";
import { C } from "@/constants/Colors";

const CALLOUT_META: Record<
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
> = {
  tip: { label: "Tip", color: "#34C759", icon: "bulb-outline" },
  note: { label: "Note", color: C.primary, icon: "information-circle-outline" },
  info: { label: "Info", color: "#007AFF", icon: "information-circle-outline" },
  warning: { label: "Warning", color: "#FF9500", icon: "warning-outline" },
  important: {
    label: "Important",
    color: "#FF3B30",
    icon: "alert-circle-outline",
  },
};

type Props = { kind: CalloutKind; content: string };

export function CalloutBlock({ kind, content }: Props) {
  const meta = CALLOUT_META[kind] ?? CALLOUT_META.note;
  const lines = content.split("\n");
  const title = lines[0]?.trim();
  const body =
    lines
      .slice(title && lines.length > 1 ? 1 : 0)
      .join("\n")
      .trim() || content;

  return (
    <CardShell
      label={title || meta.label}
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

const s = StyleSheet.create({
  body: { fontSize: 16, lineHeight: 24, color: C.text },
});
