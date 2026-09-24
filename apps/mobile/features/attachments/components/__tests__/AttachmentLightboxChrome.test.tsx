import { StyleSheet } from "react-native";
import { render } from "@testing-library/react-native";

import { AttachmentLightboxChrome } from "@/features/attachments/components/AttachmentLightboxChrome";
import { lightTheme as mockLightTheme, withAlpha } from "@/lib/theme";

jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));

const actions = {
  onClose: jest.fn(),
  onShare: jest.fn(),
  onDownload: jest.fn(),
  onToggleOverflow: jest.fn(),
  onCloseOverflow: jest.fn(),
  onUseInChat: jest.fn(),
  onOpenChat: jest.fn(),
  onDelete: jest.fn(),
};

it("derives attachment chrome from media theme tokens", async () => {
  const props = {
    visible: true,
    overflowOpen: false,
    insets: { top: 0, right: 0, bottom: 0, left: 0 },
    busy: null,
    canShare: true,
    showOverflow: true,
    showUseInChat: true,
    showOpenChat: false,
    showDelete: false,
    showDots: false,
    pageIndex: 0,
    pageCount: 1,
    ...actions,
  } as const;
  const ui = await render(<AttachmentLightboxChrome {...props} />);

  expect(StyleSheet.flatten(ui.getByLabelText("preview.close").props.style))
    .toMatchObject({
      backgroundColor: withAlpha(mockLightTheme.onMedia, 0.18),
    });

  await ui.rerender(<AttachmentLightboxChrome {...props} overflowOpen />);
  expect(
    StyleSheet.flatten(ui.getByTestId("lightbox-overflow-menu").props.style),
  ).toMatchObject({
    backgroundColor: withAlpha(mockLightTheme.mediaScrim, 0.94),
  });
});
