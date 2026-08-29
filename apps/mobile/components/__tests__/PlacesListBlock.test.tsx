import { fireEvent, render } from "@testing-library/react-native";

import { PlacesListBlock } from "@/components/PlacesListBlock";

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

describe("PlacesListBlock", () => {
  it("opens place details in AppSheet", async () => {
    const { getByText, getByTestId } = await render(
      <PlacesListBlock
        places={[
          {
            name: "Cafe Luna",
            url: "https://maps.example.com/cafe-luna",
            note: "Good espresso",
            address: "1 Main St",
          },
        ]}
      />,
    );

    await fireEvent.press(getByText("Cafe Luna"));

    expect(getByTestId("app-sheet-handle")).toBeTruthy();
    expect(getByTestId("app-sheet-dialog")).toBeTruthy();
    expect(getByText("places.open_in_maps")).toBeTruthy();
  });
});
