import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import {
  cameraUnavailableKey,
  type CameraUnavailableReason,
} from "@/features/scanner/model/cameraStatus";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";

type Props = {
  reason: CameraUnavailableReason;
  /** The system Photos picker: it needs no photo-library permission. */
  onChoosePhoto: () => void;
};

/** In place of a black viewfinder: why the camera cannot run, and a photo instead. */
export function ScannerCameraUnavailable({ reason, onChoosePhoto }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={s.center} testID={`math-scanner-camera-unavailable-${reason}`}>
      <Icon name="camera" size={IconSize.lg} color={theme.onMedia} />
      <Text style={s.text} accessibilityRole="alert" accessibilityLiveRegion="polite">
        {t(cameraUnavailableKey(reason))}
      </Text>
      <Pressable
        style={s.primary}
        onPress={onChoosePhoto}
        testID="math-scanner-unavailable-photos"
        accessibilityRole="button"
        accessibilityLabel={t("chat.math_scan_photos_a11y")}
      >
        <Text style={s.primaryText}>{t("chat.math_scan_choose_photo")}</Text>
      </Pressable>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    center: {
      ...StyleSheet.absoluteFill,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: Space.xl,
      gap: Space.md,
    },
    text: {
      ...Type.body,
      color: theme.onMedia,
      textAlign: "center",
    },
    primary: {
      backgroundColor: theme.primary,
      paddingHorizontal: Space.gutter,
      paddingVertical: Space.sm,
      borderRadius: Radius.md,
      minHeight: Space.minTouch,
      justifyContent: "center",
    },
    primaryText: {
      ...Type.label,
      color: theme.onPrimary,
      ...Weight.bold,
    },
  });
}
