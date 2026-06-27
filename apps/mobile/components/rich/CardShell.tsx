import { ReactNode, useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import { Ionicons } from "@expo/vector-icons";

import { C } from "@/constants/Colors";

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
  iconColor = C.textSecondary,
  accentColor = C.border,
  children,
}: Props) {
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
    <View style={[s.wrap, { borderLeftColor: accentColor }]}>
      <View style={s.header}>
        <View style={s.labelRow}>
          {icon ? <Ionicons name={icon} size={15} color={iconColor} /> : null}
          <Text style={s.label}>{label}</Text>
        </View>
        {copyText ? (
          <Pressable style={s.copyBtn} onPress={onCopy} hitSlop={6}>
            <Ionicons
              name={copied ? "checkmark-outline" : "copy-outline"}
              size={14}
              color={copied ? C.primary : C.textSecondary}
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

const s = StyleSheet.create({
  wrap: {
    alignSelf: "stretch",
    backgroundColor: C.bg,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
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
    borderBottomColor: C.border,
    backgroundColor: C.surface,
  },
  labelRow: { flexDirection: "row", alignItems: "center", gap: 6, flex: 1 },
  label: { fontSize: 13, fontWeight: "600", color: C.textSecondary },
  copyBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    backgroundColor: C.bg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
  },
  copyText: { fontSize: 12, fontWeight: "600", color: C.textSecondary },
  copyTextDone: { color: C.primary },
  body: { paddingHorizontal: 12, paddingVertical: 10 },
});
