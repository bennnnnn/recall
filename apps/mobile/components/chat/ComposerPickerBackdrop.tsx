import { useMemo } from "react";
import { Pressable, StyleSheet } from "react-native";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";

type Props = {
  visible: boolean;
  onClose: () => void;
};

export function ComposerPickerBackdrop({ visible, onClose }: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeS(C), [C]);

  if (!visible) return null;

  return (
    <Pressable
      style={s.backdrop}
      onPress={onClose}
      accessibilityLabel={t("chat.close_menu")}
    />
  );
}

const makeS = (C: Theme) =>
  StyleSheet.create({
    backdrop: {
      ...StyleSheet.absoluteFill,
      zIndex: 105,
      backgroundColor: C.scrim,
    },
  });
