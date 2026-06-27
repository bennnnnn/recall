import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { C } from "@/constants/Colors";

type Props = { title: string; body: string };

export function CollapsibleBlock({ title, body }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <View style={s.wrap}>
      <Pressable style={s.header} onPress={() => setOpen((v) => !v)}>
        <Ionicons
          name={open ? "chevron-down" : "chevron-forward"}
          size={16}
          color={C.textSecondary}
        />
        <Text style={s.title}>{title}</Text>
      </Pressable>
      {open ? (
        <View style={s.bodyWrap}>
          <Text style={s.body} selectable>
            {body}
          </Text>
        </View>
      ) : null}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: {
    alignSelf: "stretch",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.bg,
    marginVertical: 8,
    overflow: "hidden",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 12,
    paddingVertical: 12,
    backgroundColor: C.surface,
  },
  title: { flex: 1, fontSize: 15, fontWeight: "600", color: C.text },
  bodyWrap: {
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: C.border,
  },
  body: { fontSize: 16, lineHeight: 24, color: C.text },
});
