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
  type StyleProp,
  type ViewStyle,
  type HostInstance,
  type ScrollViewInstance,
} from "react-native";
import { GestureDetector, GestureHandlerRootView } from "react-native-gesture-handler";
import Animated from "react-native-reanimated";
import { useTranslation } from "react-i18next";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useKeyboardHeight } from "../hooks/useKeyboardHeight";
import { useAndroidBack } from "./useAndroidBack";
import { useSheetPanDismiss } from "./useSheetPanDismiss";
import { useReduceMotion } from "@/lib/reduceMotion";
import { Layer } from "@/lib/layer";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  visible: boolean;
  onClose: () => void;
  /** "bottom" anchors to the bottom edge (slide); "center" floats mid-screen (fade). */
  variant?: "bottom" | "center";
  /**
   * Lift the sheet above the OS keyboard by its height from the screen's edge
   * (`useKeyboardHeight`), in a Modal or embedded, on both platforms: no window
   * resizes for the keyboard on Android (edge to edge). Tall sheets (e.g. add
   * reminder + date) also get a max-height + scroll so the input is not pushed
   * off-screen.
   */
  keyboardAvoiding?: boolean;
  /** Render the grabber handle at the top of a bottom sheet. */
  withHandle?: boolean;
  /** Override the grabber color when using a different sheet surface. */
  handleColor?: string;
  /**
   * Scrim tap, hardware back, and pan-down all honor this. Defaults to true.
   * Pass false for a blocking sheet — onRequestClose is still wired.
   */
  backdropDismiss?: boolean;
  /** Optional tint for sheets that soften the background instead of dimming it. */
  backdropColor?: string;
  /** Extra bottom padding on top of the safe-area inset (e.g. 12 for action sheets). */
  minBottomPadding?: number;
  /**
   * Float above the bottom edge with side/bottom margins (not edge-to-edge).
   * Safe-area clearance is applied as margin so the last row stays visible.
   */
  floating?: boolean;
  /**
   * Extra lift for a floating panel, in addition to the safe area. The attach
   * sheet sits on the bottom edge over the composer, and rides up by the math
   * keyboard's height while that is open, so it still covers the composer.
   */
  bottomOffset?: number;
  /** Style override for the panel (background, radius, padding). */
  contentContainerStyle?: StyleProp<ViewStyle>;
  /**
   * Draw the sheet in the current screen instead of a Modal, so a real choice
   * Modal can open over it without moving this sheet. Android Back still closes
   * it first (`useAndroidBack`).
   */
  embedded?: boolean;
  children: ReactNode;
};

export function Sheet({
  visible,
  onClose,
  variant = "bottom",
  keyboardAvoiding = false,
  withHandle,
  handleColor,
  backdropDismiss = true,
  backdropColor,
  minBottomPadding = 0,
  floating = false,
  bottomOffset = 0,
  contentContainerStyle,
  embedded = false,
  children,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const keyboardHeight = useKeyboardHeight(keyboardAvoiding && visible);
  const reduceMotion = useReduceMotion();
  const dialogRef = useRef<HostInstance>(null);
  const scrollRef = useRef<ScrollViewInstance>(null);
  const dismissible = backdropDismiss;
  const { pan, panStyle } = useSheetPanDismiss(
    dismissible && variant === "bottom",
    reduceMotion,
    onClose,
  );

  const animation = reduceMotion ? "none" : variant === "center" ? "fade" : "slide";
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

  useEffect(() => {
    if (!visible || !keyboardAvoiding) return;
    const frame = requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ y: 0, animated: false });
    });
    return () => cancelAnimationFrame(frame);
  }, [visible, keyboardAvoiding]);

  const body = keyboardAvoiding ? (
    <ScrollView
      ref={scrollRef}
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

  const handle = showHandle ? (
    <View
      style={[s.handle, handleColor ? { backgroundColor: handleColor } : undefined]}
      testID="app-sheet-handle"
    />
  ) : null;

  const panel = (
    <View
      ref={dialogRef}
      role="dialog" // not accessibilityRole: Android's has no "dialog" (lib/__tests__/accessibilityRoles)
      accessibilityViewIsModal
      // VoiceOver's two-finger scrub closes it, as the scrim and Android back do.
      onAccessibilityEscape={dismissible ? requestClose : undefined}
      testID="app-sheet-dialog"
      collapsable={false}
      style={[
        s.panel,
        variant === "bottom" && s.panelBottom,
        variant === "center" && s.panelCenter,
        variant === "bottom" &&
          (floating
            ? {
                marginHorizontal: Space.md,
                marginBottom: keyboardOpen
                  ? Space.sm
                  : floatingSheetBottomMargin({
                      safeAreaBottom: insets.bottom,
                      bottomOffset,
                    }),
                paddingBottom: Math.max(minBottomPadding, Space.sm),
                borderRadius: Radius.sheet,
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

  const frame = (
    <View
      style={[
        s.overlay,
        variant === "center" && s.overlayCenter,
        keyboardAvoiding && variant === "bottom" && { paddingBottom: keyboardHeight },
      ]}
      testID={keyboardAvoiding ? "app-sheet-keyboard-host" : undefined}
    >
      <Pressable
        style={[s.backdrop, backdropColor ? { backgroundColor: backdropColor } : undefined]}
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
  );

  if (embedded) {
    return visible ? <EmbeddedSheet style={s.embedded} onBack={requestClose}>{frame}</EmbeddedSheet> : null;
  }

  return (
    <Modal
      visible={visible}
      transparent
      animationType={animation}
      onRequestClose={requestClose}
      testID="app-sheet-modal"
    >
      <GestureHandlerRootView style={s.flex}>{frame}</GestureHandlerRootView>
    </Modal>
  );
}

/**
 * A sheet drawn in the screen has no Modal to take Android Back for it, so it listens
 * itself from the moment it is up: Back closes it (a blocking one stays) and goes no
 * further, as it does for a sheet in a Modal. Nor is it a window of its own to a screen
 * reader: iOS skips what is drawn beside it in the screen (`accessibilityViewIsModal`);
 * the rest, and everything on Android, the screen hides with `SheetCover`.
 */
function EmbeddedSheet({
  style,
  onBack,
  children,
}: {
  style: StyleProp<ViewStyle>;
  onBack: () => void;
  children: ReactNode;
}) {
  useAndroidBack(true, onBack);
  return (
    <View style={style} accessibilityViewIsModal testID="app-sheet-embedded">
      {children}
    </View>
  );
}

/**
 * What an `embedded` sheet is drawn over: wrap the screen's content in it, beside the sheet,
 * not around it. While `covered` (the sheet is up) a screen reader skips the content. With the
 * attach sheet open, VoiceOver and TalkBack still reached the chat, its header and composer
 * behind it: Android has no modal flag, and iOS's skips only the sheet's own siblings.
 */
export function SheetCover({
  covered,
  style,
  children,
}: {
  covered: boolean;
  style?: StyleProp<ViewStyle>;
  children: ReactNode;
}) {
  return (
    <View
      style={style}
      // Uncovered, a bare View is flattened away: each open and close would create it and
      // re-parent everything under it (the list, the composer's field, header buttons).
      collapsable={false}
      accessibilityElementsHidden={covered}
      importantForAccessibility={covered ? "no-hide-descendants" : "auto"}
    >
      {children}
    </View>
  );
}

/**
 * Bottom margin for a floating sheet. Safe-area clearance, plus `bottomOffset`
 * when a caller needs the panel to end higher than the home indicator.
 */
export function floatingSheetBottomMargin(options: {
  safeAreaBottom: number;
  bottomOffset?: number;
}): number {
  const safe = Math.max(options.safeAreaBottom, Space.xs) + Space.sm;
  const offset = options.bottomOffset ?? 0;
  if (offset <= 0) return safe;
  return Math.max(safe, offset + Space.sm);
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
      padding: Space.lg,
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
      borderTopLeftRadius: Radius.sheet,
      borderTopRightRadius: Radius.sheet,
    },
    panelCenter: {
      backgroundColor: t.bg,
      borderRadius: Radius.sheet,
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
      marginTop: Space.xs,
      marginBottom: Space.xxs,
    },
    scrollContent: {
      flexGrow: 0,
    },
    embedded: {
      position: "absolute",
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      zIndex: Layer.sheet,
    },
  });
}
