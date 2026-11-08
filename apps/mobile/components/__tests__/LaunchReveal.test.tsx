import { render } from "@testing-library/react-native";

import appJson from "../../app.json";
import { LaunchReveal, SPLASH_BACKGROUND, SPLASH_ICON_SIZE } from "@/components/LaunchReveal";

jest.mock("expo-splash-screen", () => ({ preventAutoHideAsync: jest.fn(async () => {}), hide: jest.fn() }));

type SplashOptions = { image: string; imageWidth?: number; backgroundColor: string; dark?: { backgroundColor?: string } };

function splashConfig(): SplashOptions {
  const entry = (appJson.expo.plugins as unknown[]).find(
    (plugin): plugin is [string, SplashOptions] => Array.isArray(plugin) && plugin[0] === "expo-splash-screen",
  );
  if (!entry) throw new Error("app.json has no expo-splash-screen plugin");
  return entry[1];
}

it("draws the native splash again: its icon, size and both page colours", () => {
  // A reveal that differs from the native splash would jump on the first frame.
  const splash = splashConfig();
  expect(splash.image).toBe("./assets/images/splash-icon.png");
  expect(splash.imageWidth ?? 100).toBe(SPLASH_ICON_SIZE);
  expect(splash.backgroundColor).toBe(SPLASH_BACKGROUND.light);
  expect(splash.dark?.backgroundColor).toBe(SPLASH_BACKGROUND.dark);
});

it("covers the first frame, touch-through, until the splash goes", async () => {
  const { getByTestId } = await render(<LaunchReveal />);
  // Hidden from VoiceOver on purpose: it is the splash, not content.
  const page = getByTestId("launch-reveal", { includeHiddenElements: true });
  expect(page.props.pointerEvents).toBe("none");
  expect(page).toHaveStyle({ backgroundColor: SPLASH_BACKGROUND.light });
});
