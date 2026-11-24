import { useState } from "react";
import { ScrollView } from "react-native";
import { act, fireEvent, render } from "@testing-library/react-native";

import { FeatureShowcase, SLIDES } from "@/features/auth/components/landing/FeatureShowcase";

let mockReduceMotion = false;
jest.mock("@/lib/motion", () => ({
  ...jest.requireActual("@/lib/motion"),
  useReduceMotion: () => mockReduceMotion,
}));

/** The landing holds the index, as `OnboardingScreen` does. */
function Host() {
  const [index, setIndex] = useState(0);
  return <FeatureShowcase index={index} onIndexChange={setIndex} />;
}

function selected(screen: Awaited<ReturnType<typeof render>>) {
  return SLIDES.findIndex(
    (slide) => screen.getByLabelText(slide.titleKey).props.accessibilityState?.selected,
  );
}

async function showcase() {
  const screen = await render(<Host />);
  await act(async () => {
    fireEvent(screen.getByTestId("landing-showcase"), "layout", {
      nativeEvent: { layout: { width: 360, height: 500 } },
    });
  });
  return screen;
}

beforeEach(() => {
  jest.useFakeTimers();
  mockReduceMotion = false;
});
afterEach(() => jest.useRealTimers());

it("shows every feature, each with its title and words", async () => {
  const screen = await showcase();
  for (const slide of SLIDES) {
    expect(screen.getByTestId(`landing-slide-${slide.key}`)).toBeOnTheScreen();
    expect(screen.getByText(slide.bodyKey)).toBeOnTheScreen();
  }
});

it("never turns by itself, so a slide stays until it is read", async () => {
  const screen = await showcase();
  await act(async () => {
    jest.advanceTimersByTime(60_000);
  });
  expect(selected(screen)).toBe(0);
});

it("a dot takes you to any slide, and the row scrolls there", async () => {
  const scrollTo = jest.spyOn(ScrollView.prototype, "scrollTo");
  const screen = await showcase();
  await act(async () => {
    fireEvent.press(screen.getByLabelText(SLIDES[3].titleKey));
  });
  expect(selected(screen)).toBe(3);
  expect(scrollTo).toHaveBeenLastCalledWith({ x: 3 * 360, animated: true });
  scrollTo.mockRestore();
});

it("a scroll the button started never turns the slide back", async () => {
  const screen = await showcase();
  await act(async () => {
    fireEvent.press(screen.getByLabelText(SLIDES[2].titleKey));
  });
  // Android ends the programmatic scroll part way; with no finger on it, that is ignored.
  await act(async () => {
    fireEvent(screen.getByTestId("landing-showcase-row"), "momentumScrollEnd", {
      nativeEvent: { contentOffset: { x: 360 * 1 } },
    });
  });
  expect(selected(screen)).toBe(2);
});

it("a swipe sets the slide where it stops", async () => {
  const screen = await showcase();
  const row = screen.getByTestId("landing-showcase-row");
  await act(async () => {
    fireEvent(row, "scrollBeginDrag");
    fireEvent(row, "momentumScrollEnd", { nativeEvent: { contentOffset: { x: 360 * 2 } } });
  });
  expect(selected(screen)).toBe(2);
});

it("a scene takes the room the screen has, within its bounds", () => {
  const { sceneHeight } = jest.requireActual("@/features/auth/components/landing/SceneParts");
  expect(sceneHeight(640)).toBe(250); // a small Android phone still fits
  expect(sceneHeight(727)).toBe(337); // the S23 at display zoom
  expect(sceneHeight(480)).toBe(240); // smaller still: the landing scrolls
  expect(sceneHeight(1280)).toBe(380); // a tablet: no giant card
});

it("a fling still settling when a dot or Next turns the slide never turns it back", async () => {
  const screen = await showcase();
  const row = screen.getByTestId("landing-showcase-row");
  await act(async () => {
    fireEvent(row, "scrollBeginDrag");
  });
  await act(async () => {
    fireEvent.press(screen.getByLabelText(SLIDES[2].titleKey));
  });
  await act(async () => {
    fireEvent(row, "momentumScrollEnd", { nativeEvent: { contentOffset: { x: 360 * 0.4 } } });
  });
  expect(selected(screen)).toBe(2);
});

it("words inside a scene keep their size under large system text; the slide's own scale", async () => {
  const screen = await showcase();
  expect(screen.getByText("onboarding.demo_news_ask", { includeHiddenElements: true }).props.maxFontSizeMultiplier).toBe(1);
  expect(screen.getByText(SLIDES[0].bodyKey).props.maxFontSizeMultiplier).toBe(1.3);
});
