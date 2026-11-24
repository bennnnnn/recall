/**
 * What Recall does, shown before sign-in: one slide per feature, each a short scene that
 * plays when it comes on screen. The landing's Next button, a swipe or a dot turns them; they
 * never turn by themselves, so a slide stays until it is read. Under Reduce Motion every scene
 * is shown still and a turn is not animated.
 */
import { type ComponentRef, type ComponentType, useEffect, useMemo, useRef, useState } from "react";
import {
  type LayoutChangeEvent,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useTranslation } from "react-i18next";

import { useReduceMotion } from "@/lib/motion";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { ImageScene, NewsScene, ReminderScene } from "./ChatScenes";
import { PhysicsScene, ScanScene } from "./MotionScenes";
import { SceneTint } from "./SceneParts";

type Slide = {
  key: string;
  Scene: ComponentType<{ active: boolean }>;
  titleKey: string;
  bodyKey: string;
};

/** Learning first: a photo of homework worked out, then a physics answer that plays; then
 * making and asking: a picture from a sentence, today's news with its sources; then a reminder
 * from one sentence. */
export const SLIDES: readonly Slide[] = [
  { key: "scan", Scene: ScanScene, titleKey: "onboarding.slide_scan_title", bodyKey: "onboarding.slide_scan_body" },
  {
    key: "physics",
    Scene: PhysicsScene,
    titleKey: "onboarding.slide_physics_title",
    bodyKey: "onboarding.slide_physics_body",
  },
  { key: "image", Scene: ImageScene, titleKey: "onboarding.slide_image_title", bodyKey: "onboarding.slide_image_body" },
  { key: "news", Scene: NewsScene, titleKey: "onboarding.slide_chat_title", bodyKey: "onboarding.slide_chat_body" },
  {
    key: "remind",
    Scene: ReminderScene,
    titleKey: "onboarding.slide_remind_title",
    bodyKey: "onboarding.slide_remind_body",
  },
];

/** Large system text still reads, and the landing still fits on one screen. */
export const MAX_FONT_SCALE = 1.3;

type Props = {
  /** The slide on screen; the landing owns it, so its button can turn the slides. */
  index: number;
  onIndexChange: (index: number) => void;
};

export function FeatureShowcase({ index, onIndexChange }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const reduceMotion = useReduceMotion();
  const scroller = useRef<ComponentRef<typeof ScrollView>>(null);
  const [width, setWidth] = useState(0);
  // Only a finger's swipe reports where it stopped: Android also ends a scroll the button
  // started, part way, and reading that one turned the slide back.
  const swiping = useRef(false);

  // A new index from the button or a dot scrolls to it; a swipe already sits there. A fling
  // still settling when Next is tapped is over: the scroll that follows is the button's.
  useEffect(() => {
    if (width === 0) return;
    swiping.current = false;
    scroller.current?.scrollTo({ x: index * width, animated: !reduceMotion });
  }, [index, reduceMotion, width]);

  const onLayout = (event: LayoutChangeEvent) => setWidth(event.nativeEvent.layout.width);
  const onSettle = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    if (!swiping.current || width === 0) return;
    swiping.current = false;
    onIndexChange(Math.round(event.nativeEvent.contentOffset.x / width));
  };

  return (
    <View onLayout={onLayout} testID="landing-showcase">
      <ScrollView
        keyboardShouldPersistTaps="handled"
        ref={scroller}
        testID="landing-showcase-row"
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onScrollBeginDrag={() => {
          swiping.current = true;
        }}
        onMomentumScrollEnd={onSettle}
        scrollEventThrottle={16}
      >
        {SLIDES.map(({ key, Scene, titleKey, bodyKey }, slide) => (
          <View key={key} style={[s.slide, { width }]} testID={`landing-slide-${key}`}>
            <SceneTint.Provider value={theme.graphSeries[slide % theme.graphSeries.length]}>
              <Scene active={slide === index} />
            </SceneTint.Provider>
            <Text style={s.title} accessibilityRole="header" maxFontSizeMultiplier={MAX_FONT_SCALE}>
              {t(titleKey)}
            </Text>
            <Text
              style={s.body}
              maxFontSizeMultiplier={MAX_FONT_SCALE}
              textBreakStrategy="balanced"
              lineBreakStrategyIOS="push-out"
            >
              {t(bodyKey)}
            </Text>
          </View>
        ))}
      </ScrollView>
      <View style={s.dots}>
        {SLIDES.map(({ key, titleKey }, slide) => (
          <Pressable
            key={key}
            onPress={() => onIndexChange(slide)}
            hitSlop={8}
            accessibilityRole="button"
            accessibilityLabel={t(titleKey)}
            accessibilityState={{ selected: slide === index }}
          >
            <View style={[s.dot, slide === index && s.dotActive]} />
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    slide: { paddingHorizontal: 2 },
    title: { ...Type.title, color: theme.text, textAlign: "center", marginTop: Space.lg },
    body: {
      ...Type.body,
      color: theme.textSecondary,
      textAlign: "center",
      marginTop: Space.xs,
      paddingHorizontal: Space.sm,
      minHeight: 48,
    },
    dots: { flexDirection: "row", justifyContent: "center", gap: Space.xs, marginTop: Space.md },
    dot: { width: 8, height: 8, borderRadius: Radius.full, backgroundColor: theme.borderStrong },
    dotActive: { width: 22, backgroundColor: theme.primary },
  });
}
