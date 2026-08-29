import { ReactNode, useEffect, useMemo, useRef } from "react";
import {
  AccessibilityInfo,
  Dimensions,
  findNodeHandle,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
  type AccessibilityRole,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { GestureDetector, GestureHandlerRootView } from "react-native-gesture-handler";
import Animated from "react-native-reanimated";
import { useTranslation } from "react-i18next";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useKeyboardHeight } from "@/hooks/useKeyboardHeight";
import { useSheetPanDismiss } from "@/hooks/useSheetPanDismiss";
import { useReduceMotion } from "@/lib/reduceMotion";
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
  /**
   * Scrim tap, hardware back, and pan-down all honor this. Defaults to true.
   * Pass false for a blocking sheet — onRequestClose is still wired.
   */
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
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const keyboardHeight = useKeyboardHeight(keyboardAvoiding && visible);
  const reduceMotion = useReduceMotion();
  const dialogRef = useRef<View>(null);
  const dismissible = backdropDismiss;
  const { pan, panStyle } = useSheetPanDismiss(
    dismissible && variant === "bottom",
    reduceMotion,
    onClose,
  );

  const resolvedAnimation = reduceMotion
    ? "none"
    : (animation ?? (variant === "center" ? "fade" : "slide"));
  const showHandle = withHandle ?? variant === "bottom";
  const keyboardOpen = keyboardAvoiding && keyboardHeight > 0;
  const windowHeight = Dimensions.get("window").height;
  const panelMaxHeight =
    keyboardAvoiding && variant === "bottom"
      ? Math.max(200, windowHeight - keyboardHeight - Math.max(insets.top, 12))
      : undefined;

  const requestClose = () => {
    if (dismissible) onClose();
  };

  useEffect(() => {
    if (!visible) return;
    const frame = requestAnimationFrame(() => {
      const tag = findNodeHandle(dialogRef.current);
      if (tag != null) AccessibilityInfo.setAccessibilityFocus(tag);
    });
    return () => cancelAnimationFrame(frame);
  }, [visible]);

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

  const handle = showHandle ? <View style={s.handle} testID="app-sheet-handle" /> : null;

  const panel = (
    <View
      ref={dialogRef}
      accessibilityRole={"dialog" as AccessibilityRole}
      accessibilityViewIsModal
      testID="app-sheet-dialog"
      collapsable={false}
      style={[
        s.panel,
        variant === "bottom" && s.panelBottom,
        variant === "center" && s.panelCenter,
        variant === "bottom" &&
          (floating
            ? {
                marginHorizontal: 16,
                marginBottom: keyboardOpen ? 12 : Math.max(insets.bottom, 8) + 12,
                paddingBottom: Math.max(minBottomPadding, 12),
                borderRadius: 20,
              }
            : {
                paddingBottom: keyboardOpen
                  ? Math.max(minBottomPadding, 8)
                  : Math.max(insets.bottom, minBottomPadding),
              }),
        contentContainerStyle,
        panelMaxHeight != null && { maxHeight: panelMaxHeight },
      ]}
    >
      {dismissible && variant === "bottom" ? (
        <GestureDetector gesture={pan}>
          <Animated.View style={s.handleHit}>
            {handle ?? <View style={s.handleHitFill} />}
          </Animated.View>
        </GestureDetector>
      ) : (
        handle
      )}
      {body}
    </View>
  );

  return (
    <Modal
      visible={visible}
      transparent
      animationType={resolvedAnimation}
      onRequestClose={requestClose}
      testID="app-sheet-modal"
    >
      <GestureHandlerRootView style={s.flex}>
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
            onPress={dismissible ? requestClose : undefined}
            accessibilityLabel={dismissible ? t("common.close") : undefined}
            accessibilityRole={dismissible ? "button" : undefined}
            accessible={dismissible}
            testID="app-sheet-backdrop"
          />
          {dismissible && variant === "bottom" ? (
            <Animated.View style={panStyle}>{panel}</Animated.View>
          ) : (
            panel
          )}
        </View>
      </GestureHandlerRootView>
    </Modal>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    flex: { flex: 1 },
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
    handleHit: {
      minHeight: 24,
      alignItems: "center",
      justifyContent: "center",
    },
    handleHitFill: {
      height: 24,
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
