import { existsSync } from "fs";
import { join } from "path";

import appJson from "../../app.json";
import { APP_FONT_FACES } from "@/lib/appFonts";

// The package's index also exports a useFonts hook that needs expo-font's native module.
jest.mock("@expo-google-fonts/space-mono", () => ({ SpaceMono_400Regular: 1 }));
// Asset ids, as Metro hands them over; jest does not transform katex's files.
jest.mock("katex/dist/fonts/KaTeX_Main-Regular.ttf", () => 2);
jest.mock("katex/dist/fonts/KaTeX_Math-Italic.ttf", () => 3);
jest.mock("katex/dist/fonts/KaTeX_AMS-Regular.ttf", () => 4);
jest.mock("katex/dist/fonts/KaTeX_Size1-Regular.ttf", () => 5);

type AndroidFont = { fontFamily: string; fontDefinitions: { path: string; weight: number }[] };

declare const __dirname: string;
const APP_ROOT = join(__dirname, "..", "..");

function androidFonts(): AndroidFont[] {
  const plugins: readonly unknown[] = appJson.expo.plugins;
  for (const entry of plugins) {
    if (Array.isArray(entry) && entry[0] === "expo-font") {
      return (entry[1] as { android: { fonts: AndroidFont[] } }).android.fonts;
    }
  }
  throw new Error("app.json has no expo-font options");
}

describe("app fonts", () => {
  it("embeds every face on Android under the name the app draws it by", () => {
    // A face missing here would be loaded at every Android launch instead.
    const embedded = androidFonts().map((font) => font.fontFamily).sort();
    expect(embedded).toEqual(Object.keys(APP_FONT_FACES).sort());
  });

  it("points each embedded face at one regular-slot file that exists", () => {
    for (const font of androidFonts()) {
      expect(font.fontDefinitions).toHaveLength(1);
      // Styles ask for weight 400 on every face (lib/type.ts); a heavier slot draws Roboto.
      expect(font.fontDefinitions[0].weight).toBe(400);
      expect(existsSync(join(APP_ROOT, font.fontDefinitions[0].path))).toBe(true);
    }
  });
});
