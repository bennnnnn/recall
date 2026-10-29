import { useMemo } from "react";
import { StyleSheet, Text } from "react-native";
import { useTranslation } from "react-i18next";

import { type Theme, useTheme } from "@/lib/theme";
import { DYNAMIC_TYPE_MAX, Type, Weight } from "@/lib/type";

type Props = {
  /** `media`: white ink for a dark plate over the camera. `card`: secondary ink on the review card. */
  appearance: "media" | "card";
};

/**
 * Where a scanned photo goes: to Recall, and from there to third-party AI
 * providers that read it (privacy policy, "AI Processing and Other Services
 * That Receive Your Data"). Every scanner screen a photo can leave from shows
 * it just above the control that sends it, so it is seen, and reached by a
 * screen reader, before acting.
 *
 * Capped like the composer: it shares a fixed layout with the camera controls
 * and the review's buttons, which a larger size would push off the screen.
 */
export function ScanPhotoDisclosure({ appearance }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <Text style={appearance === "media" ? s.media : s.card} maxFontSizeMultiplier={DYNAMIC_TYPE_MAX}>
      {t("chat.math_scan_photo_disclosure")}
    </Text>
  );
}

function makeStyles(theme: Theme) {
  const line = { ...Type.caption, ...Weight.regular, textAlign: "center" } as const;
  return StyleSheet.create({
    media: { ...line, color: theme.onMedia },
    card: { ...line, color: theme.textSecondary },
  });
}
