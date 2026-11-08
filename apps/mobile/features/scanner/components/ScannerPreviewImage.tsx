import { Image, StyleSheet, View } from "react-native";

import type { ScanRegion } from "@/lib/math/scannerRegion";
import { useTheme } from "@/lib/theme";

type Props = {
  uri: string;
  /** Where the still is drawn, as a region of the view; the whole view until it is measured. */
  frame: ScanRegion | null;
  view: { width: number; height: number };
};

/** The still on the crop screen, contained in the space between the scanner's controls. */
export function ScannerPreviewImage({ uri, frame, view }: Props) {
  const theme = useTheme();
  return (
    <View style={[StyleSheet.absoluteFill, { backgroundColor: theme.mediaScrim }]}>
      <Image
        source={{ uri }}
        testID="math-scanner-preview"
        style={frame ? {
          position: "absolute",
          left: frame.x * view.width,
          top: frame.y * view.height,
          width: frame.width * view.width,
          height: frame.height * view.height,
        } : StyleSheet.absoluteFill}
        resizeMode="contain"
      />
    </View>
  );
}
