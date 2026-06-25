/**
 * Custom slide drawer — no react-native-gesture-handler required.
 * Works in Expo Go. The chat is always rendered; the sidebar slides
 * in from the left as an animated overlay.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Animated, Pressable, StyleSheet, useWindowDimensions, View } from 'react-native';
import { Slot } from 'expo-router';

import { ConversationList } from '@/components/ConversationList';
import { C } from '@/constants/Colors';
import { DrawerProvider } from '@/contexts/DrawerContext';
import { registerDrawer } from '@/lib/drawer';

export default function DrawerLayout() {
  const { width } = useWindowDimensions();
  const DRAWER_WIDTH = width * 0.82;
  const translateX = useRef(new Animated.Value(-DRAWER_WIDTH)).current;
  const overlayOpacity = useRef(new Animated.Value(0)).current;
  const [drawerOpen, setDrawerOpen] = useState(false);

  const open = useCallback(() => {
    setDrawerOpen(true);
    Animated.parallel([
      Animated.spring(translateX, { toValue: 0, useNativeDriver: true, friction: 20, tension: 200 }),
      Animated.timing(overlayOpacity, { toValue: 1, duration: 200, useNativeDriver: true }),
    ]).start();
  }, [overlayOpacity, translateX]);

  const close = useCallback(() => {
    setDrawerOpen(false);
    Animated.parallel([
      Animated.spring(translateX, { toValue: -DRAWER_WIDTH, useNativeDriver: true, friction: 20, tension: 200 }),
      Animated.timing(overlayOpacity, { toValue: 0, duration: 150, useNativeDriver: true }),
    ]).start();
  }, [overlayOpacity, translateX, DRAWER_WIDTH]);

  useEffect(() => {
    registerDrawer(open, close);
  }, [open, close]);

  // Fake navigation prop for ConversationList
  const fakeNav = { openDrawer: open, closeDrawer: close } as any;
  const fakeProps = { navigation: fakeNav } as any;

  return (
    <DrawerProvider value={{ isOpen: drawerOpen, open, close }}>
      <View style={s.root}>
        <View style={s.rootInner}>
        {/* Main content — chat screen sits behind drawer when open */}
        <View
          style={[s.content, drawerOpen && s.contentBehind]}
          pointerEvents={drawerOpen ? 'none' : 'auto'}>
          <Slot />
        </View>

        {/* Dark overlay when drawer is open */}
        <Animated.View
          pointerEvents="none"
          style={[s.overlay, { opacity: overlayOpacity }]}
        />

        {/* Tap-to-close overlay — only active when drawer is open */}
        <Animated.View
          pointerEvents={drawerOpen ? 'auto' : 'none'}
          style={[s.tapClose, { opacity: overlayOpacity }]}>
          <Pressable style={StyleSheet.absoluteFill} onPress={close} />
        </Animated.View>

        {/* Drawer panel — above chat header */}
        <Animated.View
          style={[s.drawer, { width: DRAWER_WIDTH, transform: [{ translateX }] }]}>
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
    backgroundColor: 'rgba(0,0,0,0.35)',
    zIndex: 150,
  },
  tapClose: {
    ...StyleSheet.absoluteFill,
    zIndex: 160,
  },
  drawer: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    left: 0,
    backgroundColor: C.bg,
    shadowColor: '#000',
    shadowOpacity: 0.18,
    shadowRadius: 20,
    shadowOffset: { width: 4, height: 0 },
    elevation: 24,
    zIndex: 200,
    overflow: 'hidden',
  },
});
