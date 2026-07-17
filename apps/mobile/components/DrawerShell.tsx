/**
 * Custom slide drawer. Chat stays mounted; the sidebar slides in from the
 * left. Open via the header button, Android back, or an interactive swipe
 * from the left edge; close via scrim tap, back, or swipe left.
 */
/* eslint-disable react-hooks/immutability -- Reanimated shared values are mutated on the UI thread by design */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { BackHandler, Pressable, StyleSheet, useWindowDimensions, View } from "react-native";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import Animated, {
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from "react-native-reanimated";

import { ConversationList } from "@/components/ConversationList";
import { DrawerProvider } from "@/contexts/DrawerContext";
import { registerDrawer } from "@/lib/drawer";
import { tap } from "@/lib/haptics";
import { Motion } from "@/lib/motion";
import { useTheme } from "@/lib/theme";

/** Left-edge hit slop for swipe-to-open (pt). */
const EDGE_WIDTH = 28;
/** Fraction of drawer width that counts as "open enough" to finish open. */
const OPEN_PROGRESS = 0.35;
/** Horizontal velocity (px/s from RNGH) to fling open/closed. */
const FLING_VX = 800;

const SPRING = { damping: 28, stiffness: 280 } as const;

export function DrawerShell({ children }: { children: ReactNode }) {
  const { width } = useWindowDimensions();
  const theme = useTheme();
  const drawerWidth = width * 0.82;

  const translateX = useSharedValue(-drawerWidth);
  const overlayOpacity = useSharedValue(0);
  const dragStartX = useSharedValue(-drawerWidth);
  const widthSV = useSharedValue(drawerWidth);
  const [drawerOpen, setDrawerOpen] = useState(false);
  /** Keep the edge strip interactive through an in-progress open drag. */
  const [edgeArmed, setEdgeArmed] = useState(true);
  const drawerOpenRef = useRef(false);
  drawerOpenRef.current = drawerOpen;

  useEffect(() => {
    widthSV.value = drawerWidth;
    if (!drawerOpenRef.current) {
      translateX.value = -drawerWidth;
    }
  }, [drawerWidth, translateX, widthSV]);

  const disarmEdge = useCallback(() => {
    setEdgeArmed(false);
  }, []);

  const settleTo = useCallback(
    (open: boolean, withHaptic: boolean) => {
      const w = widthSV.value;
      setDrawerOpen(open);
      drawerOpenRef.current = open;
      if (withHaptic && open) tap();
      if (!open) setEdgeArmed(true);
      translateX.value = withSpring(open ? 0 : -w, SPRING, (finished) => {
        if (finished && open) {
          runOnJS(disarmEdge)();
        }
      });
      overlayOpacity.value = withTiming(open ? 1 : 0, {
        duration: open ? Motion.duration.snappy : 150,
      });
    },
    [disarmEdge, overlayOpacity, translateX, widthSV],
  );

  const settleToRef = useRef(settleTo);
  settleToRef.current = settleTo;

  const settleFromGesture = useCallback((openNext: boolean, withHaptic: boolean) => {
    settleToRef.current(openNext, withHaptic);
  }, []);

  const markOpen = useCallback(() => {
    setDrawerOpen(true);
    drawerOpenRef.current = true;
  }, []);

  const open = useCallback(() => settleToRef.current(true, true), []);
  const close = useCallback(() => settleToRef.current(false, false), []);

  useEffect(() => {
    registerDrawer(open, close);
  }, [open, close]);

  useEffect(() => {
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (!drawerOpenRef.current) return false;
      close();
      return true;
    });
    return () => sub.remove();
  }, [close]);

  const openFromEdge = useMemo(
    () =>
      Gesture.Pan()
        .activeOffsetX(10)
        .failOffsetY([-12, 12])
        .onStart(() => {
          dragStartX.value = translateX.value;
          runOnJS(markOpen)();
        })
        .onUpdate((e) => {
          const w = widthSV.value;
          const next = Math.max(-w, Math.min(0, dragStartX.value + e.translationX));
          translateX.value = next;
          overlayOpacity.value = 1 + next / w;
        })
        .onEnd((e) => {
          const w = widthSV.value;
          const next = Math.max(-w, Math.min(0, dragStartX.value + e.translationX));
          const progress = 1 + next / w;
          const flingOpen = e.velocityX > FLING_VX;
          const flingClose = e.velocityX < -FLING_VX;
          const shouldOpen = flingOpen || (!flingClose && progress >= OPEN_PROGRESS);
          runOnJS(settleFromGesture)(shouldOpen, shouldOpen && progress < 1);
        })
        .onFinalize((_e, success) => {
          if (!success) {
            const progress = 1 + translateX.value / widthSV.value;
            runOnJS(settleFromGesture)(progress >= OPEN_PROGRESS, false);
          }
        }),
    [dragStartX, markOpen, overlayOpacity, settleFromGesture, translateX, widthSV],
  );

  const closeFromScrim = useMemo(
    () =>
      Gesture.Pan()
        .activeOffsetX(-10)
        .failOffsetY([-12, 12])
        .onStart(() => {
          dragStartX.value = translateX.value;
        })
        .onUpdate((e) => {
          const w = widthSV.value;
          const next = Math.max(-w, Math.min(0, dragStartX.value + e.translationX));
          translateX.value = next;
          overlayOpacity.value = 1 + next / w;
        })
        .onEnd((e) => {
          const w = widthSV.value;
          const next = Math.max(-w, Math.min(0, dragStartX.value + e.translationX));
          const progress = 1 + next / w;
          const flingOpen = e.velocityX > FLING_VX;
          const flingClose = e.velocityX < -FLING_VX;
          const shouldOpen = flingOpen || (!flingClose && progress >= OPEN_PROGRESS);
          runOnJS(settleFromGesture)(shouldOpen, false);
        })
        .onFinalize((_e, success) => {
          if (!success) {
            const progress = 1 + translateX.value / widthSV.value;
            runOnJS(settleFromGesture)(progress >= OPEN_PROGRESS, false);
          }
        }),
    [dragStartX, overlayOpacity, settleFromGesture, translateX, widthSV],
  );

  const drawerStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: translateX.value }],
  }));

  const overlayStyle = useAnimatedStyle(() => ({
    opacity: overlayOpacity.value,
  }));

  const fakeNav = { openDrawer: open, closeDrawer: close } as any;
  const fakeProps = { navigation: fakeNav } as any;
  const drawerValue = useMemo(
    () => ({ isOpen: drawerOpen, open, close }),
    [drawerOpen, open, close],
  );

  return (
    <DrawerProvider value={drawerValue}>
      <View style={s.root}>
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
              { backgroundColor: theme.scrim },
              overlayStyle,
              { pointerEvents: "none" },
            ]}
          />

          <GestureDetector gesture={closeFromScrim}>
            <Animated.View
              style={[
                s.tapClose,
                overlayStyle,
                { pointerEvents: drawerOpen ? "auto" : "none" },
              ]}
            >
              <Pressable style={StyleSheet.absoluteFill} onPress={close} />
            </Animated.View>
          </GestureDetector>

          <Animated.View
            style={[
              s.drawer,
              {
                width: drawerWidth,
                backgroundColor: theme.bg,
                pointerEvents: drawerOpen ? "auto" : "none",
              },
              drawerStyle,
            ]}
          >
            <ConversationList {...fakeProps} />
          </Animated.View>

          <GestureDetector gesture={openFromEdge}>
            <View
              style={s.edgeHit}
              collapsable={false}
              pointerEvents={edgeArmed ? "auto" : "none"}
            />
          </GestureDetector>
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
  edgeHit: {
    position: "absolute",
    top: 0,
    bottom: 0,
    left: 0,
    width: EDGE_WIDTH,
    zIndex: 210,
  },
});
