import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/ui/icons/Icon";

import { RichBodyText } from "@/components/rich/RichBodyText";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { IconSize } from "@/ui/icons/sizes";

type Props = { title: string; body: string };

export function CollapsibleBlock({ title, body }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [open, setOpen] = useState(false);

  return (
    <View style={s.wrap}>
      <Pressable
        style={s.header}
        onPress={() => setOpen((v) => !v)}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={title}
      >
        <Icon
          name={open ? "chevron-down" : "chevron-right"}
          size={IconSize.xs}
          color={theme.textSecondary}
        />
        <Text style={s.title}>{title}</Text>
      </Pressable>
      {open ? (
        <View style={s.bodyWrap}>
          <RichBodyText style={s.body} selectable>
            {body}
          </RichBodyText>
        </View>
      ) : null}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: {
      alignSelf: "stretch",
      borderRadius: Radius.md,
      borderWidth: 1,
      borderColor: t.border,
      backgroundColor: t.bg,
      marginVertical: Space.xs,
      overflow: "hidden",
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.sm,
      backgroundColor: t.surface,
    },
    title: { flex: 1, ...Type.callout, color: t.text },
    bodyWrap: {
      paddingHorizontal: Space.sm,
      paddingVertical: 10,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.border,
    },
    body: { ...Type.body, lineHeight: 24, color: t.text },
  });
}
