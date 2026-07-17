import { ReactNode, useEffect, useMemo, useState } from "react";
import {
  Dimensions,
  Keyboard,
  Modal,
  Platform,
  Pressable,
  ScrollView,
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
  /**
   * Lift the sheet above the OS keyboard. Uses Keyboard events (not
   * KeyboardAvoidingView) so Android Modals work — activity `resize` does not
   * apply inside RN Modal windows. Tall sheets (e.g. add reminder + date)
   * also get a max-height + scroll so the input is not pushed off-screen.
   */
  keyboardAvoiding?: boolean;
  /** Render the grabber handle at the top of a bottom sheet. */
  withHandle?: boolean;
  /** Allow tapping the scrim to dismiss. Defaults to true. */
  backdropDismiss?: boolean;
  /** Extra bottom padding on top of the safe-area inset (e.g. 12 for action sheets). */
  minBottomPadding?: number;
  /**
   * Float above the bottom edge with side/bottom margins (not edge-to-edge).
   * Safe-area clearance is applied as margin so the last row stays visible.
   */
  floating?: boolean;
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
  floating = false,
  contentContainerStyle,
  children,
}: Props) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [keyboardHeight, setKeyboardHeight] = useState(0);

  useEffect(() => {
    if (!keyboardAvoiding || !visible) {
      setKeyboardHeight(0);
      return;
    }
    const showEvent = Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow";
    const hideEvent = Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide";
    const showSub = Keyboard.addListener(showEvent, (e) => {
      setKeyboardHeight(Math.max(0, e.endCoordinates.height));
    });
    const hideSub = Keyboard.addListener(hideEvent, () => setKeyboardHeight(0));
    return () => {
      showSub.remove();
      hideSub.remove();
    };
  }, [keyboardAvoiding, visible]);

  const resolvedAnimation = animation ?? (variant === "center" ? "fade" : "slide");
  const showHandle = withHandle ?? variant === "bottom";
  const keyboardOpen = keyboardAvoiding && keyboardHeight > 0;
  const windowHeight = Dimensions.get("window").height;
  // Leave a little air under the status area so a tall reminder sheet can scroll
  // instead of shoving the text field under the notch / off the top.
  const panelMaxHeight =
    keyboardAvoiding && variant === "bottom"
      ? Math.max(200, windowHeight - keyboardHeight - Math.max(insets.top, 12))
      : undefined;

  const body = keyboardAvoiding ? (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      bounces={false}
      showsVerticalScrollIndicator={false}
      contentContainerStyle={s.scrollContent}
    >
      {children}
    </ScrollView>
  ) : (
    children
  );

  const content = (
    <View
      style={[
        s.panel,
        variant === "bottom" && s.panelBottom,
        variant === "center" && s.panelCenter,
        variant === "bottom" &&
          (floating
            ? {
                marginHorizontal: 16,
                marginBottom: keyboardOpen
                  ? 12
                  : Math.max(insets.bottom, 8) + 12,
                paddingBottom: Math.max(minBottomPadding, 12),
                borderRadius: 20,
              }
            : {
                // Home indicator is covered while the keyboard is up — drop safe-area pad.
                paddingBottom: keyboardOpen
                  ? Math.max(minBottomPadding, 8)
                  : Math.max(insets.bottom, minBottomPadding),
              }),
        contentContainerStyle,
        // After style overrides so tall sheets (reminder + date) still clamp.
        panelMaxHeight != null && { maxHeight: panelMaxHeight },
      ]}
    >
      {showHandle ? <View style={s.handle} testID="app-sheet-handle" /> : null}
      {body}
    </View>
  );

  return (
    <Modal
      visible={visible}
      transparent
      animationType={resolvedAnimation}
      onRequestClose={backdropDismiss ? onClose : undefined}
    >
      <View
        style={[
          s.overlay,
          variant === "center" && s.overlayCenter,
          keyboardAvoiding && variant === "bottom" && { paddingBottom: keyboardHeight },
        ]}
        testID={keyboardAvoiding ? "app-sheet-keyboard-host" : undefined}
      >
        <Pressable
          style={s.backdrop}
          onPress={backdropDismiss ? onClose : undefined}
          accessibilityLabel={backdropDismiss ? "Close sheet" : undefined}
          accessibilityRole={backdropDismiss ? "button" : undefined}
          testID="app-sheet-backdrop"
        />
        {content}
      </View>
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
    scrollContent: {
      flexGrow: 0,
    },
  });
}
