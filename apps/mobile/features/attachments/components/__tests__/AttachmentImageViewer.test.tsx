import { act, fireEvent, render } from "@testing-library/react-native";
import { StyleSheet } from "react-native";

import { ensureLocalAttachmentFile } from "@/features/attachments/model/downloadChatAttachment";
import { AttachmentImageViewer } from "@/features/attachments/components/AttachmentImageViewer";
import { lightTheme as mockLightTheme } from "@/lib/theme";

jest.mock("@/contexts/AuthContext", () => ({
  useAuthToken: () => "tok",
}));
jest.mock("@/features/attachments/model/attachmentUri", () => ({
  resolveAttachmentUri: ({ attachmentId }: { attachmentId?: string }) => `http://test.local/${attachmentId}`,
  attachmentRequestHeaders: (uri: string, token: string) => uri.startsWith("http://test.local/") ? { Authorization: `Bearer ${token}` } : {},
}));
jest.mock("@/features/attachments/model/downloadChatAttachment", () => ({
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
    const firstSource = getByTestId("attachment-viewer-image").props.source;
    await act(async () => {
      getByTestId("attachment-viewer-image").props.onError();
    });
    await fireEvent.press(getByTestId("media-load-retry"));
    expect(getByTestId("attachment-viewer-image")).toBeTruthy();
    expect(queryByTestId("media-load-retry")).toBeNull();
    expect(getByTestId("attachment-viewer-image").props.source.cacheKey).not.toBe(
      firstSource.cacheKey,
    );
  });

  it("keeps auth headers, cached loading, and decoded aspect sizing", async () => {
    const view = await render(
      <AttachmentImageViewer visible attachmentId="a" />,
    );
    const image = view.getByTestId("attachment-viewer-image");
    expect(image.props.source).toEqual({
      uri: "http://test.local/a",
      headers: { Authorization: "Bearer tok" },
      cacheKey: "attachment:0:0:http://test.local/a",
    });
    expect(image.props.contentFit).toBe("contain");
    expect(image.props.cachePolicy).toBe("memory-disk");

    await fireEvent(view.getByTestId("attachment-viewer-tap"), "layout", {
      nativeEvent: { layout: { width: 400, height: 300 } },
    });
    await fireEvent(image, "load", {
      nativeEvent: { source: { width: 800, height: 400 } },
    });
    expect(view.getByTestId("attachment-viewer-image")).toHaveStyle({
      width: 400,
      height: 200,
    });
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
    expect(view.getByTestId("attachment-viewer-image").props.source).toEqual({
      uri: "http://test.local/first",
      headers: { Authorization: "Bearer tok" },
      cacheKey: "attachment:1:0:http://test.local/first",
    });
  });

  it("pages across photos from the same generation", async () => {
    const { getByTestId } = await render(
      <AttachmentImageViewer
        visible
        images={[
          { attachmentId: "a", path: "/attachments/a/file" },
          { attachmentId: "b", path: "/attachments/b/file" },
        ]}
        initialIndex={0}
      />,
    );
    const pager = getByTestId("attachment-viewer-pager");
    expect(pager.props.horizontal).toBe(true);
    expect(pager.props.pagingEnabled).toBe(true);
    expect(getByTestId("attachment-image-viewer")).toBeTruthy();
  });

  it("hides Open chat when the visible photo is not linked to a chat", async () => {
    const { getByLabelText, queryByLabelText } = await render(
      <AttachmentImageViewer
        visible
        images={[{ attachmentId: "a" }]}
        onOpenChat={jest.fn()}
        onDelete={jest.fn()}
      />,
    );
    await fireEvent.press(getByLabelText("preview.more_a11y"));
    expect(queryByLabelText("gallery.open_chat_a11y")).toBeNull();
    expect(getByLabelText("common.delete")).toBeTruthy();
  });

  it("opens chat for the visible Library photo from the more menu", async () => {
    const onOpenChat = jest.fn();
    const { getByLabelText, queryByLabelText } = await render(
      <AttachmentImageViewer
        visible
        images={[{ attachmentId: "a", chatId: "c1" }]}
        onOpenChat={onOpenChat}
      />,
    );
    expect(queryByLabelText("gallery.open_chat_a11y")).toBeNull();
    await fireEvent.press(getByLabelText("preview.more_a11y"));
    await fireEvent.press(getByLabelText("gallery.open_chat_a11y"));
    expect(onOpenChat).toHaveBeenCalledWith(expect.objectContaining({ attachmentId: "a", chatId: "c1" }));
  });

  it("keeps only share, download, and more in the header", async () => {
    const { getByLabelText, queryByLabelText } = await render(
      <AttachmentImageViewer
        visible
        images={[{ attachmentId: "a", chatId: "c1" }]}
        onOpenChat={jest.fn()}
        onUseInChat={jest.fn()}
        onDelete={jest.fn()}
      />,
    );
    expect(getByLabelText("preview.close")).toBeTruthy();
    expect(getByLabelText("preview.share")).toBeTruthy();
    expect(getByLabelText("common.download")).toBeTruthy();
    expect(getByLabelText("preview.more_a11y")).toBeTruthy();
    expect(queryByLabelText("gallery.use_in_chat")).toBeNull();
    expect(queryByLabelText("common.delete")).toBeNull();
  });

  it("hides chrome on a tap and brings it back on the next tap", async () => {
    const { getByTestId, getByLabelText, queryByLabelText } = await render(
      <AttachmentImageViewer visible attachmentId="a" />,
    );
    expect(getByLabelText("preview.close")).toBeTruthy();
    await fireEvent.press(getByTestId("attachment-viewer-tap"));
    expect(queryByLabelText("preview.close")).toBeNull();
    expect(queryByLabelText("preview.share")).toBeNull();
    await fireEvent.press(getByTestId("attachment-viewer-tap"));
    expect(getByLabelText("preview.close")).toBeTruthy();
    expect(getByLabelText("preview.share")).toBeTruthy();
  });

  it("puts each header icon on its own circular chip", async () => {
    const { getByLabelText } = await render(
      <AttachmentImageViewer visible attachmentId="a" />,
    );
    const close = StyleSheet.flatten(getByLabelText("preview.close").props.style);
    expect(close.backgroundColor).toBeTruthy();
    expect(close.borderRadius).toBeGreaterThan(20);
    const share = StyleSheet.flatten(getByLabelText("preview.share").props.style);
    expect(share.backgroundColor).toBe(close.backgroundColor);
  });

  it("slides the lightbox so a downward pull can dismiss it", async () => {
    const { getByTestId } = await render(
      <AttachmentImageViewer visible attachmentId="a" />,
    );
    const root = getByTestId("attachment-image-viewer");
    expect(root.props.collapsable).toBe(false);
    // Pan translateY composed with the scale-in entrance (0.94 → 1 on open).
    expect(StyleSheet.flatten(root.props.style).transform).toEqual([
      { translateY: 0 },
      { scale: 0.94 },
    ]);
  });
});
