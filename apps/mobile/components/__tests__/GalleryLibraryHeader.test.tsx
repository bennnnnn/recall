import { fireEvent, render } from "@testing-library/react-native";

import { GalleryLibraryHeader } from "@/components/gallery/GalleryLibraryHeader";
import { lightTheme as mockLightTheme } from "@/lib/theme";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));

jest.mock("@/lib/haptics", () => ({
  tap: jest.fn(),
}));

describe("GalleryLibraryHeader", () => {
  it("puts the layout toggle next to the Files tab", async () => {
    const onToggleLayout = jest.fn();
    const { getByTestId, getByLabelText } = await render(
      <GalleryLibraryHeader
        filter="all"
        searchQuery=""
        layout="column"
        onSearchChange={jest.fn()}
        onFilterChange={jest.fn()}
        onToggleLayout={onToggleLayout}
      />,
    );

    expect(getByLabelText("gallery.filter.files")).toBeTruthy();
    expect(getByTestId("gallery-layout-toggle")).toBeTruthy();
    await fireEvent.press(getByTestId("gallery-layout-toggle"));
    expect(onToggleLayout).toHaveBeenCalled();
  });
});
