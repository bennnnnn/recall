import { act, fireEvent, render } from "@testing-library/react-native";

import { ensureLocalAttachmentFile } from "@/lib/downloadChatAttachment";
import { AttachmentImageViewer } from "@/components/AttachmentImageViewer";
import { lightTheme as mockLightTheme } from "@/lib/theme";

jest.mock("@/contexts/AuthContext", () => ({
  useAuthToken: () => "tok",
}));
jest.mock("@/lib/attachmentUri", () => ({
  resolveAttachmentUri: ({ attachmentId }: { attachmentId?: string }) => `http://test.local/${attachmentId}`,
  attachmentRequestHeaders: (uri: string, token: string) => uri.startsWith("http://test.local/") ? { Authorization: `Bearer ${token}` } : {},
}));
jest.mock("@/lib/downloadChatAttachment", () => ({
  ensureLocalAttachmentFile: jest.fn(() => new Promise(() => {})),
  getCachedAttachmentFile: () => null,
  invalidateCachedAttachmentFile: jest.fn(),
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

let mockGeneration = 0;
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockGeneration }));

describe("AttachmentImageViewer", () => {
  beforeEach(() => { mockGeneration = 0; jest.mocked(ensureLocalAttachmentFile).mockReset().mockImplementation(() => new Promise(() => {})); });
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
  it("never displays a previous image's cached file when the selected attachment changes", async () => {
    jest.mocked(ensureLocalAttachmentFile).mockResolvedValueOnce("file:///cache/first.jpg");
    const view = await render(<AttachmentImageViewer visible attachmentId="first" />);
    expect(view.getByTestId("attachment-viewer-image").props.source.uri).toBe("file:///cache/first.jpg");
    await view.rerender(<AttachmentImageViewer visible attachmentId="second" />);
    expect(view.getByTestId("attachment-viewer-image").props.source.uri).toBe("http://test.local/second");
  });

  it("does not attach authorization to an external preview URL", async () => {
    const view = await render(<AttachmentImageViewer visible attachmentId="first" previewUri="https://external.test/preview.jpg" />);
    expect(view.getByTestId("attachment-viewer-image").props.source).toEqual({ uri: "https://external.test/preview.jpg" });
  });

  it("detaches a cached image when the account changes", async () => {
    jest.mocked(ensureLocalAttachmentFile).mockResolvedValueOnce("file:///cache/previous-account.jpg");
    const view = await render(<AttachmentImageViewer visible attachmentId="first" />);
    mockGeneration++;
    await view.rerender(<AttachmentImageViewer visible attachmentId="first" />);
    expect(view.getByTestId("attachment-viewer-image").props.source.uri).toBe("http://test.local/first");
  });

});
