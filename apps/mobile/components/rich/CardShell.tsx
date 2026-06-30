import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import { Ionicons } from "@expo/vector-icons";

import { Theme, useTheme } from "@/lib/theme";

type Props = {
  label: string;
  copyText?: string;
  icon?: keyof typeof Ionicons.glyphMap;
  iconColor?: string;
  accentColor?: string;
  children: ReactNode;
};

export function CardShell({
  label,
  copyText,
  icon,
  iconColor,
  accentColor,
  children,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const resolvedIconColor = iconColor ?? theme.textSecondary;
  const resolvedAccent = accentColor ?? theme.border;
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const onCopy = async () => {
    if (!copyText?.trim()) return;
    await Clipboard.setStringAsync(copyText);
    setCopied(true);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setCopied(false), 1500);
  };

  return (
    <View style={[s.wrap, { borderLeftColor: resolvedAccent }]}>
      <View style={s.header}>
        <View style={s.labelRow}>
          {icon ? <Ionicons name={icon} size={15} color={resolvedIconColor} /> : null}
          <Text style={s.label}>{label}</Text>
        </View>
        {copyText ? (
          <Pressable style={s.copyBtn} onPress={onCopy} hitSlop={6}>
            <Ionicons
              name={copied ? "checkmark-outline" : "copy-outline"}
              size={14}
              color={copied ? theme.primary : theme.textSecondary}
            />
            <Text style={[s.copyText, copied && s.copyTextDone]}>
              {copied ? "Copied" : "Copy"}
            </Text>
          </Pressable>
        ) : null}
      </View>
      <View style={s.body}>{children}</View>
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: {
      alignSelf: "stretch",
      backgroundColor: t.bg,
      borderRadius: 12,
      borderWidth: 1,
      borderColor: t.border,
      borderLeftWidth: 3,
      marginVertical: 8,
      overflow: "hidden",
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 8,
      paddingHorizontal: 12,
      paddingVertical: 9,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
      backgroundColor: t.surface,
    },
    labelRow: { flexDirection: "row", alignItems: "center", gap: 6, flex: 1 },
    label: { fontSize: 13, fontWeight: "600", color: t.textSecondary },
    copyBtn: {
      flexDirection: "row",
      alignItems: "center",
      gap: 4,
      paddingHorizontal: 8,
      paddingVertical: 4,
      borderRadius: 8,
      backgroundColor: t.bg,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
    },
    copyText: { fontSize: 12, fontWeight: "600", color: t.textSecondary },
    copyTextDone: { color: t.primary },
    body: { paddingHorizontal: 12, paddingVertical: 10 },
  });
}
