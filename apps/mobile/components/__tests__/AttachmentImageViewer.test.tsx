import { act, fireEvent, render } from "@testing-library/react-native";

import { AttachmentImageViewer } from "@/components/AttachmentImageViewer";
import { lightTheme as mockLightTheme } from "@/lib/theme";

jest.mock("@/contexts/AuthContext", () => ({
  useAuthToken: () => "tok",
}));
jest.mock("@/lib/attachmentUri", () => ({
  resolveAttachmentUri: () => "http://test.local/a",
}));
jest.mock("@/lib/downloadChatAttachment", () => ({
  ensureLocalAttachmentFile: jest.fn(() => new Promise(() => {})),
  getCachedAttachmentFile: () => null,
  saveChatAttachmentToLibrary: jest.fn(),
  shareChatAttachment: jest.fn(),
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));

describe("AttachmentImageViewer", () => {
  it("shows Retry after the image fails instead of spinning forever", async () => {
    const { getByTestId, queryByTestId } = await render(
      <AttachmentImageViewer visible attachmentId="a" />,
    );
    expect(getByTestId("attachment-viewer-image")).toBeTruthy();
    await act(async () => {
      getByTestId("attachment-viewer-image").props.onError();
    });
    expect(queryByTestId("attachment-viewer-image")).toBeNull();
    expect(getByTestId("media-load-retry")).toBeTruthy();
  });

  it("reloads the image when Retry is pressed", async () => {
    const { getByTestId, queryByTestId } = await render(
      <AttachmentImageViewer visible attachmentId="a" />,
    );
    await act(async () => {
      getByTestId("attachment-viewer-image").props.onError();
    });
    await fireEvent.press(getByTestId("media-load-retry"));
    expect(getByTestId("attachment-viewer-image")).toBeTruthy();
    expect(queryByTestId("media-load-retry")).toBeNull();
  });
});
