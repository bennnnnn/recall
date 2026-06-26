import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import { Ionicons } from "@expo/vector-icons";

import { C } from "@/constants/Colors";

type Props = {
  text: string;
  label?: string;
};

export function CopyBlock({ text, label }: Props) {
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    await Clipboard.setStringAsync(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <View style={s.wrap}>
      <View style={[s.header, !label && s.headerCompact]}>
        {label ? <Text style={s.label}>{label}</Text> : null}
        <Pressable style={s.copyBtn} onPress={onCopy} hitSlop={6}>
          <Ionicons
            name={copied ? "checkmark-outline" : "copy-outline"}
            size={15}
            color={copied ? C.primary : C.textSecondary}
          />
          <Text style={[s.copyText, copied && s.copyTextDone]}>
            {copied ? "Copied" : "Copy"}
          </Text>
        </Pressable>
      </View>
      <Text style={s.body} selectable>
        {text}
      </Text>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: {
    alignSelf: "stretch",
    width: "100%",
    maxWidth: "100%",
    backgroundColor: C.contentSurface,
    borderRadius: 12,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
    marginVertical: 8,
    overflow: "hidden",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
    backgroundColor: C.contentSurface,
  },
  headerCompact: {
    justifyContent: "flex-end",
    paddingVertical: 8,
  },
  label: {
    flex: 1,
    flexShrink: 1,
    fontSize: 13,
    fontWeight: "600",
    color: C.textSecondary,
  },
  copyBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    flexShrink: 0,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
    backgroundColor: C.bg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
  },
  copyText: { fontSize: 13, fontWeight: "600", color: C.textSecondary },
  copyTextDone: { color: C.primary },
  body: {
    flexShrink: 1,
    fontSize: 16,
    lineHeight: 24,
    color: C.text,
    paddingHorizontal: 14,
    paddingVertical: 12,
    backgroundColor: C.contentSurface,
  },
});
