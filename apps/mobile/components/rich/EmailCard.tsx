import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { CardShell } from "@/components/rich/CardShell";
import { EmailDraft } from "@/lib/richBlocks";
import { Theme, useTheme } from "@/lib/theme";

type Props = { draft: EmailDraft };

function fullEmailText(draft: EmailDraft): string {
  const parts: string[] = [];
  if (draft.to) parts.push(`To: ${draft.to}`);
  if (draft.subject) parts.push(`Subject: ${draft.subject}`);
  if (parts.length) parts.push("");
  parts.push(draft.body);
  return parts.join("\n");
}

export function EmailCard({ draft }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <CardShell
      label="Email draft"
      copyText={fullEmailText(draft)}
      icon="mail-outline"
      accentColor={theme.primary}
    >
      {draft.to ? (
        <View style={s.row}>
          <Text style={s.key}>To</Text>
          <Text style={s.value} selectable>
            {draft.to}
          </Text>
        </View>
      ) : null}
      {draft.subject ? (
        <View style={s.row}>
          <Text style={s.key}>Subject</Text>
          <Text style={[s.value, s.subject]} selectable>
            {draft.subject}
          </Text>
        </View>
      ) : null}
      <Text style={s.body} selectable>
        {draft.body}
      </Text>
    </CardShell>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    row: {
      flexDirection: "row",
      gap: 10,
      marginBottom: 8,
      alignItems: "flex-start",
    },
    key: { width: 58, fontSize: 13, fontWeight: "600", color: t.textSecondary },
    value: { flex: 1, fontSize: 15, lineHeight: 21, color: t.text },
    subject: { fontWeight: "600" },
    body: { fontSize: 16, lineHeight: 24, color: t.text, marginTop: 4 },
  });
}
