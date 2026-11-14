import { act, render } from "@testing-library/react-native";

import { AnswerPhotoPlaceholder } from "@/features/images/components/AnswerPhotoPlaceholder";

/**
 * 2026-11-09: "where is Ethiopia" showed "finding a photo", then the reply came without one.
 * A photo still on its way at `done` now has a placeholder of the photo's size that says so,
 * until the photo comes (the bubble then shows the photo) or its wait ends with none.
 */
jest.mock("react-i18next", () => {
  const en = jest.requireActual("@/lib/i18n/en.json") as Record<string, string>;
  return { useTranslation: () => ({ t: (key: string) => en[key] ?? key }) };
});
jest.mock("@/features/attachments/components/ChatMessageImage", () => ({
  useThumbnailSize: () => ({ width: 148, height: 189 }),
}));
jest.mock("expo-linear-gradient", () => {
  const { View: MockView } = jest.requireActual("react-native");
  return { LinearGradient: MockView };
});

const NOW = Date.parse("2026-11-09T14:58:00Z");

describe("AnswerPhotoPlaceholder", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.setSystemTime(NOW);
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("stays, the photo's size and saying a photo is coming, while the photo is on its way", async () => {
    const view = await render(<AnswerPhotoPlaceholder until={NOW + 20_000} />);
    const card = view.getByTestId("answer-photo-placeholder");
    expect(card).toHaveStyle({ width: 148, height: 189 });
    expect(view.getByLabelText("Finding a photo…")).toBeTruthy();
    await act(async () => {
      jest.advanceTimersByTime(19_999);
    });
    expect(view.queryByTestId("answer-photo-placeholder")).toBeTruthy();
  });

  it("goes when the wait ends with no photo", async () => {
    const view = await render(<AnswerPhotoPlaceholder until={NOW + 20_000} />);
    await act(async () => {
      jest.advanceTimersByTime(20_000);
    });
    expect(view.queryByTestId("answer-photo-placeholder")).toBeNull();
  });

  it("shows nothing for a wait already over (a reply read back later)", async () => {
    const view = await render(<AnswerPhotoPlaceholder until={NOW - 1} />);
    expect(view.queryByTestId("answer-photo-placeholder")).toBeNull();
  });
});
