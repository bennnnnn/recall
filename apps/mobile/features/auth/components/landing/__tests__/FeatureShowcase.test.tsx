import { act, fireEvent, render } from "@testing-library/react-native";

import { FeatureShowcase, SLIDE_MS, SLIDES } from "@/features/auth/components/landing/FeatureShowcase";

let mockReduceMotion = false;
jest.mock("@/lib/motion", () => ({
  ...jest.requireActual("@/lib/motion"),
  useReduceMotion: () => mockReduceMotion,
}));

function selected(screen: Awaited<ReturnType<typeof render>>) {
  return SLIDES.findIndex(
    (slide) => screen.getByLabelText(slide.titleKey).props.accessibilityState?.selected,
  );
}

async function showcase() {
  const screen = await render(<FeatureShowcase />);
  // The slides turn once the row knows its width.
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

it("turns to the next slide by itself, and a dot takes you to any", async () => {
  const screen = await showcase();
  expect(selected(screen)).toBe(0);
  await act(async () => {
    jest.advanceTimersByTime(SLIDE_MS);
  });
  expect(selected(screen)).toBe(1);
  await act(async () => {
    fireEvent.press(screen.getByLabelText(SLIDES[4].titleKey));
  });
  expect(selected(screen)).toBe(4);
});

it("never turns by itself under Reduce Motion", async () => {
  mockReduceMotion = true;
  const screen = await showcase();
  await act(async () => {
    jest.advanceTimersByTime(SLIDE_MS * 3);
  });
  expect(selected(screen)).toBe(0);
});
