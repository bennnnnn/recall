import { ReactNode, useMemo } from "react";
import {
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Theme, useTheme } from "@/lib/theme";

type Props = {
  visible: boolean;
  onClose: () => void;
  /** "bottom" anchors to the bottom edge (slide); "center" floats mid-screen (fade). */
  variant?: "bottom" | "center";
  animation?: "slide" | "fade" | "none";
  /** Wrap content in a KeyboardAvoidingView (for sheets with text inputs). */
  keyboardAvoiding?: boolean;
  /** Render the grabber handle at the top of a bottom sheet. */
  withHandle?: boolean;
  /** Allow tapping the scrim to dismiss. Defaults to true. */
  backdropDismiss?: boolean;
  /** Extra bottom padding on top of the safe-area inset (e.g. 12 for action sheets). */
  minBottomPadding?: number;
  /** Style override for the panel (background, radius, padding). */
  contentContainerStyle?: StyleProp<ViewStyle>;
  children: ReactNode;
};

export function AppSheet({
  visible,
  onClose,
  variant = "bottom",
  animation,
  keyboardAvoiding = false,
  withHandle,
  backdropDismiss = true,
  minBottomPadding = 0,
  contentContainerStyle,
  children,
}: Props) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const s = useMemo(() => makeStyles(theme), [theme]);

  const resolvedAnimation = animation ?? (variant === "center" ? "fade" : "slide");
  const showHandle = withHandle ?? variant === "bottom";

  const content = (
    <View
      style={[
        s.panel,
        variant === "bottom" && s.panelBottom,
        variant === "center" && s.panelCenter,
        variant === "bottom" && {
          paddingBottom: Math.max(insets.bottom, minBottomPadding),
        },
        contentContainerStyle,
      ]}
    >
      {showHandle ? <View style={s.handle} testID="app-sheet-handle" /> : null}
      {children}
    </View>
  );

  return (
    <Modal
      visible={visible}
      transparent
      animationType={resolvedAnimation}
      onRequestClose={backdropDismiss ? onClose : undefined}
    >
      <KeyboardAvoidingView
        style={[s.overlay, variant === "center" && s.overlayCenter]}
        behavior={keyboardAvoiding && Platform.OS === "ios" ? "padding" : undefined}
      >
        <Pressable
          style={s.backdrop}
          onPress={backdropDismiss ? onClose : undefined}
          accessibilityLabel={backdropDismiss ? "Close sheet" : undefined}
          accessibilityRole={backdropDismiss ? "button" : undefined}
          testID="app-sheet-backdrop"
        />
        {content}
      </KeyboardAvoidingView>
    </Modal>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    overlay: {
      flex: 1,
      justifyContent: "flex-end",
    },
    overlayCenter: {
      justifyContent: "center",
      alignItems: "center",
      padding: 24,
    },
    backdrop: {
      ...StyleSheet.absoluteFill,
      backgroundColor: t.scrim,
    },
    panel: {
      overflow: "hidden",
    },
    panelBottom: {
      backgroundColor: t.bg,
      borderTopLeftRadius: 20,
      borderTopRightRadius: 20,
    },
    panelCenter: {
      backgroundColor: t.bg,
      borderRadius: 20,
      width: "100%",
      maxWidth: 420,
    },
    handle: {
      alignSelf: "center",
      width: 36,
      height: 4,
      borderRadius: 2,
      backgroundColor: t.border,
      marginTop: 8,
      marginBottom: 4,
    },
  });
}
