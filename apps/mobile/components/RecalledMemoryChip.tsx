import { useEffect, useMemo, useRef } from "react";
import { Animated, StyleSheet } from "react-native";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";

type Props = {
  count: number;
};

export function RecalledMemoryChip({ count }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const opacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    opacity.setValue(0);
    Animated.timing(opacity, {
      toValue: 1,
      duration: 420,
      useNativeDriver: true,
    }).start();
  }, [count, opacity]);

  if (count <= 0) return null;

  return (
    <Animated.Text style={[s.chip, { opacity }]}>
      {t("chat.recalled_memories", { count })}
    </Animated.Text>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    chip: {
      fontSize: 12,
      lineHeight: 16,
      color: theme.textTertiary,
      marginBottom: 6,
    },
  });
}
