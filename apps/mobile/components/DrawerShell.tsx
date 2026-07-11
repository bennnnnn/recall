/**
 * Custom slide drawer — no react-native-gesture-handler required.
 * Works in Expo Go. The chat is always rendered; the sidebar slides
 * in from the left as an animated overlay.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Animated,
  BackHandler,
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

export function DrawerShell({ children }: { children: ReactNode }) {
  const { width } = useWindowDimensions();
  const theme = useTheme();
  const DRAWER_WIDTH = width * 0.82;
  const translateX = useRef(new Animated.Value(-DRAWER_WIDTH)).current;
  const overlayOpacity = useRef(new Animated.Value(0)).current;
  const [drawerOpen, setDrawerOpen] = useState(false);

  const open = useCallback(() => {
    tap();
    setDrawerOpen(true);
    Animated.parallel([
      Animated.spring(translateX, {
        toValue: 0,
        useNativeDriver: true,
        friction: 20,
        tension: 200,
      }),
      Animated.timing(overlayOpacity, {
        toValue: 1,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start();
  }, [overlayOpacity, translateX]);

  const close = useCallback(() => {
    setDrawerOpen(false);
    Animated.parallel([
      Animated.spring(translateX, {
        toValue: -DRAWER_WIDTH,
        useNativeDriver: true,
        friction: 20,
        tension: 200,
      }),
      Animated.timing(overlayOpacity, {
        toValue: 0,
        duration: 150,
        useNativeDriver: true,
      }),
    ]).start();
  }, [overlayOpacity, translateX, DRAWER_WIDTH]);

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
            style={[s.overlay, { opacity: overlayOpacity, backgroundColor: theme.scrim }, { pointerEvents: "none" }]}
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
              { width: DRAWER_WIDTH, transform: [{ translateX }], backgroundColor: theme.bg },
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
