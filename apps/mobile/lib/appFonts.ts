/**
 * Every face the app draws with, by the family name its styles use.
 *
 * Android builds embed each face under that same name (the expo-font plugin
 * in app.json; `lib/__tests__/appFonts.test.tsx` keeps the two lists equal),
 * so `useFonts` finds them registered and loads nothing there. iOS and Expo Go
 * register them at launch, behind the splash. iOS stays on runtime loading on
 * purpose: it would find an embedded face by its own family or PostScript
 * name, and React Native then picks the face within that family by the
 * style's weight and slant, which would draw the italic files upright (styles
 * set fontStyle "normal" on them) and react-native-svg's semibold labels
 * regular. The alias a runtime load registers names exactly one face.
 *
 * One file per face: Space Mono and the KaTeX faces Skia also draws come from
 * assets/fonts, the files the plugin embeds.
 */
import type { FontSource } from "expo-font";

import {
  CODE_FONT,
  MATH_FONT,
  MATH_SIZE1_FONT,
  MATH_SYMBOL_FONT,
  MATH_VARIABLE_FONT,
} from "@/lib/fonts";

export const APP_FONT_FACES: Record<string, FontSource> = {
  [CODE_FONT]: require("@/assets/fonts/SpaceMono-Regular.ttf"),
  [MATH_FONT]: require("@/assets/fonts/KaTeX_Main-Regular.ttf"),
  [MATH_VARIABLE_FONT]: require("@/assets/fonts/KaTeX_Math-Italic.ttf"),
  [MATH_SYMBOL_FONT]: require("@/assets/fonts/KaTeX_AMS-Regular.ttf"),
  // ∬ ∭ ∮ on the math keyboard live only in this face.
  [MATH_SIZE1_FONT]: require("katex/dist/fonts/KaTeX_Size1-Regular.ttf"),
};
