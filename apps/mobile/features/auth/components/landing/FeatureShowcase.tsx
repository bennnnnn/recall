/**
 * What Recall does, shown before sign-in: one slide per feature, each a short scene that
 * plays when it comes on screen. The slides turn by themselves; a swipe or a dot takes over,
 * and the turning waits while a finger is on them. Under Reduce Motion they never turn by
 * themselves and every scene is shown still.
 */
import { type ComponentRef, type ComponentType, useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { ChatScene, HomeworkScene, ReminderScene } from "./ChatScenes";
import { PhysicsScene, ScanScene } from "./MotionScenes";
import { SceneTint } from "./SceneParts";

type Slide = {
  key: string;
  Scene: ComponentType<{ active: boolean }>;
  titleKey: string;
  bodyKey: string;
};

/** The strongest moment first: a photo of homework turning into its worked answer. */
export const SLIDES: readonly Slide[] = [
  { key: "scan", Scene: ScanScene, titleKey: "onboarding.slide_scan_title", bodyKey: "onboarding.slide_scan_body" },
  {
    key: "homework",
    Scene: HomeworkScene,
    titleKey: "onboarding.slide_homework_title",
    bodyKey: "onboarding.slide_homework_body",
  },
  { key: "chat", Scene: ChatScene, titleKey: "onboarding.slide_chat_title", bodyKey: "onboarding.slide_chat_body" },
  {
    key: "physics",
    Scene: PhysicsScene,
    titleKey: "onboarding.slide_physics_title",
    bodyKey: "onboarding.slide_physics_body",
  },
  {
    key: "remind",
    Scene: ReminderScene,
    titleKey: "onboarding.slide_remind_title",
    bodyKey: "onboarding.slide_remind_body",
  },
];

/** Long enough for a scene to play through and its words to be read. */
export const SLIDE_MS = 5000;

export function FeatureShowcase() {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const reduceMotion = useReduceMotion();
  const scroller = useRef<ComponentRef<typeof ScrollView>>(null);
  const [width, setWidth] = useState(0);
  const [index, setIndex] = useState(0);
  const [holding, setHolding] = useState(false);

  const goTo = useCallback(
    (next: number) => {
      setIndex(next);
      scroller.current?.scrollTo({ x: next * width, animated: !reduceMotion });
    },
    [reduceMotion, width],
  );

  // Each slide gets its full time: a new index, or a finger lifted, starts the clock again.
  useEffect(() => {
    if (reduceMotion || holding || width === 0) return;
    const timer = setTimeout(() => goTo((index + 1) % SLIDES.length), SLIDE_MS);
    return () => clearTimeout(timer);
  }, [goTo, holding, index, reduceMotion, width]);

  const onLayout = (event: LayoutChangeEvent) => setWidth(event.nativeEvent.layout.width);
  const onSettle = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    setHolding(false);
    if (width > 0) setIndex(Math.round(event.nativeEvent.contentOffset.x / width));
  };

  return (
    <View onLayout={onLayout} testID="landing-showcase">
      <ScrollView
        ref={scroller}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onScrollBeginDrag={() => setHolding(true)}
        onMomentumScrollEnd={onSettle}
        onScrollEndDrag={() => setHolding(false)}
        scrollEventThrottle={16}
      >
        {SLIDES.map(({ key, Scene, titleKey, bodyKey }, slide) => (
          <View key={key} style={[s.slide, { width }]} testID={`landing-slide-${key}`}>
            <SceneTint.Provider value={theme.graphSeries[slide % theme.graphSeries.length]}>
              <Scene active={slide === index} />
            </SceneTint.Provider>
            <Text style={s.title} accessibilityRole="header">{t(titleKey)}</Text>
            <Text style={s.body}>{t(bodyKey)}</Text>
          </View>
        ))}
      </ScrollView>
      <View style={s.dots}>
        {SLIDES.map(({ key, titleKey }, slide) => (
          <Pressable
            key={key}
            onPress={() => goTo(slide)}
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
