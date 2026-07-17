/**
 * Custom slide drawer. Chat stays mounted; the sidebar slides in from the
 * left. Open via the header button, Android back, or an interactive swipe
 * from the left edge; close via scrim tap, back, or swipe left.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Animated,
  BackHandler,
  PanResponder,
  Pressable,
  StyleSheet,
  useWindowDimensions,
  View,
} from "react-native";

import { ConversationList } from "@/components/ConversationList";
import { DrawerProvider } from "@/contexts/DrawerContext";
import { registerDrawer } from "@/lib/drawer";
import { tap } from "@/lib/haptics";
import { useTheme } from "@/lib/theme";

/** Left-edge hit slop for swipe-to-open (pt). */
const EDGE_WIDTH = 28;
/** Fraction of drawer width that counts as "open enough" to finish open. */
const OPEN_PROGRESS = 0.35;
/** Horizontal velocity (px/ms-ish from PanResponder) to fling open/closed. */
const FLING_VX = 0.45;

export function DrawerShell({ children }: { children: ReactNode }) {
  const { width } = useWindowDimensions();
  const theme = useTheme();
  const drawerWidth = width * 0.82;
  const drawerWidthRef = useRef(drawerWidth);
  drawerWidthRef.current = drawerWidth;

  const translateX = useRef(new Animated.Value(-drawerWidth)).current;
  const overlayOpacity = useRef(new Animated.Value(0)).current;
  const [drawerOpen, setDrawerOpen] = useState(false);
  const drawerOpenRef = useRef(false);
  drawerOpenRef.current = drawerOpen;

  const dragStartX = useRef(-drawerWidth);

  // Keep the closed position in sync when the window width changes.
  useEffect(() => {
    if (!drawerOpenRef.current) {
      translateX.setValue(-drawerWidth);
    }
  }, [drawerWidth, translateX]);

  const animateTo = useCallback(
    (open: boolean, withHaptic: boolean) => {
      if (withHaptic && open) tap();
      setDrawerOpen(open);
      drawerOpenRef.current = open;
      const w = drawerWidthRef.current;
      Animated.parallel([
        Animated.spring(translateX, {
          toValue: open ? 0 : -w,
          useNativeDriver: true,
          friction: 20,
          tension: 200,
        }),
        Animated.timing(overlayOpacity, {
          toValue: open ? 1 : 0,
          duration: open ? 200 : 150,
          useNativeDriver: true,
        }),
      ]).start();
    },
    [overlayOpacity, translateX],
  );

  const open = useCallback(() => animateTo(true, true), [animateTo]);
  const close = useCallback(() => animateTo(false, false), [animateTo]);

  useEffect(() => {
    registerDrawer(open, close);
  }, [open, close]);

  useEffect(() => {
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (!drawerOpen) return false;
      close();
      return true;
    });
    return () => sub.remove();
  }, [drawerOpen, close]);

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_e, g) => {
          if (Math.abs(g.dx) < 10) return false;
          if (Math.abs(g.dy) >= Math.abs(g.dx)) return false;
          if (!drawerOpenRef.current) {
            // Swipe right from the left edge only.
            return g.x0 <= EDGE_WIDTH && g.dx > 0;
          }
          // Swipe left on the dimmed scrim only — not on the drawer, so row
          // Swipeable actions (archive/delete) keep working.
          return g.x0 >= drawerWidthRef.current && g.dx < 0;
        },
        onPanResponderGrant: () => {
          translateX.stopAnimation((value) => {
            dragStartX.current = value;
          });
          overlayOpacity.stopAnimation();
          // Reveal chrome / allow list load as soon as the gesture claims.
          if (!drawerOpenRef.current) {
            setDrawerOpen(true);
            drawerOpenRef.current = true;
          }
        },
        onPanResponderMove: (_e, g) => {
          const w = drawerWidthRef.current;
          const next = Math.max(-w, Math.min(0, dragStartX.current + g.dx));
          translateX.setValue(next);
          overlayOpacity.setValue(1 + next / w);
        },
        onPanResponderRelease: (_e, g) => {
          const w = drawerWidthRef.current;
          const next = Math.max(-w, Math.min(0, dragStartX.current + g.dx));
          const progress = 1 + next / w;
          const flingOpen = g.vx > FLING_VX;
          const flingClose = g.vx < -FLING_VX;
          const shouldOpen = flingOpen || (!flingClose && progress >= OPEN_PROGRESS);
          animateTo(shouldOpen, shouldOpen && progress < 1);
        },
        onPanResponderTerminate: () => {
          const w = drawerWidthRef.current;
          translateX.stopAnimation((value) => {
            const progress = 1 + value / w;
            animateTo(progress >= OPEN_PROGRESS, false);
          });
        },
      }),
    [animateTo, overlayOpacity, translateX],
  );

  const fakeNav = { openDrawer: open, closeDrawer: close } as any;
  const fakeProps = { navigation: fakeNav } as any;
  const drawerValue = useMemo(
    () => ({ isOpen: drawerOpen, open, close }),
    [drawerOpen, open, close],
  );

  return (
    <DrawerProvider value={drawerValue}>
      <View style={s.root} {...panResponder.panHandlers}>
        <View style={s.rootInner}>
          <View
            style={[
              s.content,
              drawerOpen && s.contentBehind,
              { pointerEvents: drawerOpen ? "none" : "auto" },
            ]}
          >
            {children}
          </View>

          <Animated.View
            style={[
              s.overlay,
              { opacity: overlayOpacity, backgroundColor: theme.scrim },
              { pointerEvents: "none" },
            ]}
          />

          <Animated.View
            style={[
              s.tapClose,
              { opacity: overlayOpacity },
              { pointerEvents: drawerOpen ? "auto" : "none" },
            ]}
          >
            <Pressable style={StyleSheet.absoluteFill} onPress={close} />
          </Animated.View>

          <Animated.View
            style={[
              s.drawer,
              {
                width: drawerWidth,
                transform: [{ translateX }],
                backgroundColor: theme.bg,
                pointerEvents: drawerOpen ? "auto" : "none",
              },
            ]}
          >
            <ConversationList {...fakeProps} />
          </Animated.View>
        </View>
      </View>
    </DrawerProvider>
  );
}

const s = StyleSheet.create({
  root: { flex: 1 },
  rootInner: { flex: 1 },
  content: { flex: 1, zIndex: 1 },
  contentBehind: { zIndex: 0 },
  overlay: {
    ...StyleSheet.absoluteFill,
    zIndex: 150,
  },
  tapClose: {
    ...StyleSheet.absoluteFill,
    zIndex: 160,
  },
  drawer: {
    position: "absolute",
    top: 0,
    bottom: 0,
    left: 0,
    boxShadow: "4 0 20 0 rgba(0, 0, 0, 0.18)",
    elevation: 24,
    zIndex: 200,
    overflow: "hidden",
  },
});
