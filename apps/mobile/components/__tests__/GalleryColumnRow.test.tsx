import { fireEvent, render } from "@testing-library/react-native";

import { GalleryColumnRow } from "@/components/gallery/GalleryColumnRow";
import type { AttachmentListItem } from "@/lib/api";
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

jest.mock("@/components/GalleryThumbnail", () => {
  const { View } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    GalleryThumbnail: () => <View testID="gallery-column-thumb" />,
  };
});

function fileItem(): AttachmentListItem {
  return {
    id: "a",
    content_type: "application/pdf",
    size_bytes: 12,
    download_url: "/attachments/a/file",
    source: "upload",
    created_at: "2026-01-01T00:00:00.000Z",
    original_filename: "notes.pdf",
    chat_title: "Trip",
  };
}

describe("GalleryColumnRow", () => {
  it("puts the filename to the right of the thumb and shows the chat title", async () => {
    const onPress = jest.fn();
    const { getByText } = await render(
      <GalleryColumnRow
        item={fileItem()}
        fileName="notes.pdf"
        onPress={onPress}
        onLongPress={jest.fn()}
        onMissing={jest.fn()}
      />,
    );

    expect(getByText("notes.pdf")).toBeTruthy();
    expect(getByText("Trip")).toBeTruthy();
    await fireEvent.press(getByText("notes.pdf"));
    expect(onPress).toHaveBeenCalled();
  });
});
