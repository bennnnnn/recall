import { fireEvent, render } from "@testing-library/react-native";

import { SearchSourcesStack } from "@/components/SearchSourcesStack";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));

jest.mock("@/lib/reduceMotion", () => ({
  useReduceMotion: () => false,
}));

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 34, left: 0, right: 0 }),
}));

describe("SearchSourcesStack", () => {
  it("opens sources in AppSheet with a scrollable list", async () => {
    const { getByText, getByTestId } = await render(
      <SearchSourcesStack
        sources={[
          {
            url: "https://example.com/rain",
            title: "Rainfall averages",
            snippet: "January through December",
          },
        ]}
      />,
    );

    await fireEvent.press(getByText("Sources"));

    expect(getByTestId("app-sheet-handle")).toBeTruthy();
    expect(getByTestId("app-sheet-dialog")).toBeTruthy();
    expect(getByText("Rainfall averages")).toBeTruthy();
  });
});
