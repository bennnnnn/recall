import { act, fireEvent, render } from "@testing-library/react-native";

import { ComposerAttachmentPreview } from "@/features/attachments/components/ComposerAttachmentPreview";
import type { PendingAttachment } from "@/features/attachments/model/attachments";
import { shareLocalFile } from "@/lib/share/file";

jest.mock("@/ui/icons/Icon", () => ({ Icon: "Icon" }));
jest.mock("@/lib/share/file", () => ({ ...jest.requireActual("@/lib/share/file"), shareLocalFile: jest.fn() }));
const mockWarning = jest.fn();
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => ({ warning: mockWarning }) }));
jest.mock("@/features/attachments/components/LazyDraftAttachmentViewers", () => {
  const { Pressable, View } = jest.requireActual("react-native");
  const viewer = (testID: string) =>
    function MockViewer({ visible, localUri, fileName, onShare, sharing }: {
      visible: boolean;
      localUri: string;
      fileName: string;
      onShare: () => void;
      sharing?: boolean;
    }) {
      return visible ? (
        <View testID={testID} accessibilityHint={localUri} accessibilityLabel={fileName}>
          <Pressable testID="viewer-share" onPress={onShare} accessibilityState={{ busy: Boolean(sharing) }} />
        </View>
      ) : null;
    };
  return {
    LazyAttachmentPdfViewer: viewer("pdf-viewer"),
    LazyAttachmentTextViewer: viewer("text-viewer"),
    LazyComposerImageEnlarge: ({ visible, uri, onClose }: { visible: boolean; uri: string; onClose: () => void }) =>
      visible ? <Pressable testID="enlarged" accessibilityHint={uri} onPress={onClose} /> : null,
  };
});

const file = (contentType: string, fileName: string): PendingAttachment => ({
  kind: "file",
  localUri: `file:///${fileName}`,
  contentType,
  fileName,
});

describe("a picked attachment, seen before it is sent", () => {
  it("enlarges the photo over the chat on a tap, and a tap closes it", async () => {
    const view = await render(
      <ComposerAttachmentPreview
        attachment={{ kind: "image", localUri: "file:///scan.jpg", fileName: "scan.jpg", contentType: "image/jpeg" }}
        onRemove={jest.fn()}
      />,
    );
    expect(view.queryByTestId("enlarged")).toBeNull();
    await fireEvent.press(view.getByLabelText("chat.image_view_a11y"));
    expect(view.getByTestId("enlarged").props.accessibilityHint).toBe("file:///scan.jpg");
    await fireEvent.press(view.getByTestId("enlarged"));
    expect(view.queryByTestId("enlarged")).toBeNull();
  });

  it("opens a PDF in its reader and a text file in the text viewer, from the phone's copy", async () => {
    const pdf = await render(
      <ComposerAttachmentPreview attachment={file("application/pdf", "notes.pdf")} onRemove={jest.fn()} />,
    );
    await fireEvent.press(pdf.getByTestId("composer-file-open"));
    expect(pdf.getByTestId("pdf-viewer").props.accessibilityHint).toBe("file:///notes.pdf");

    const text = await render(
      <ComposerAttachmentPreview attachment={file("text/plain", "notes.txt")} onRemove={jest.fn()} />,
    );
    await fireEvent.press(text.getByTestId("composer-file-open"));
    expect(text.getByTestId("text-viewer").props.accessibilityHint).toBe("file:///notes.txt");
  });

  // A second tap on Share while the first sheet was opening was refused on Android, and the
  // viewer said sharing failed.
  it("shares the picked file once while its sheet is open, and spins meanwhile", async () => {
    let close: () => void = () => {};
    jest.mocked(shareLocalFile).mockImplementationOnce(() => new Promise<void>((resolve) => { close = resolve; }));
    const view = await render(
      <ComposerAttachmentPreview attachment={file("application/pdf", "notes.pdf")} onRemove={jest.fn()} />,
    );
    await fireEvent.press(view.getByTestId("composer-file-open"));
    await fireEvent.press(view.getByTestId("viewer-share"));
    await fireEvent.press(view.getByTestId("viewer-share"));
    expect(shareLocalFile).toHaveBeenCalledTimes(1);
    expect(mockWarning).toHaveBeenCalledWith("common.share_in_progress");
    expect(view.getByTestId("viewer-share").props.accessibilityState.busy).toBe(true);
    await act(async () => close());
    expect(view.getByTestId("viewer-share").props.accessibilityState.busy).toBe(false);
  });

  it("leaves a file nothing can show as a plain row", async () => {
    const view = await render(
      <ComposerAttachmentPreview attachment={file("application/zip", "photos.zip")} onRemove={jest.fn()} />,
    );
    expect(view.getByTestId("composer-file-open").props.accessibilityState?.disabled).toBe(true);
  });
});

describe("a long paste in the composer", () => {
  const pasted: PendingAttachment = {
    ...file("text/plain", "pasted-text.txt"),
    localUri: "file:///cache/PastedText/paste-1.txt",
    pasted: { chars: 12_345, preview: "It was a bright cold day in April" },
  };

  it("shows its first words, that it was pasted and how long it is", async () => {
    const view = await render(<ComposerAttachmentPreview attachment={pasted} onRemove={jest.fn()} />);
    expect(view.getByText("It was a bright cold day in April")).toBeTruthy();
    expect(view.getByText("chat.pasted_text · chat.pasted_text_chars")).toBeTruthy();
    expect(view.getByTestId("composer-file-open").props.accessibilityLabel).toBe("chat.pasted_text_open_a11y");
  });

  it("opens the whole text in the text viewer, and × removes it", async () => {
    const onRemove = jest.fn();
    const view = await render(<ComposerAttachmentPreview attachment={pasted} onRemove={onRemove} />);
    await fireEvent.press(view.getByTestId("composer-file-open"));
    expect(view.getByTestId("text-viewer").props.accessibilityHint).toBe("file:///cache/PastedText/paste-1.txt");
    // Titled as the chip names it, not by the file the phone wrote.
    expect(view.getByTestId("text-viewer").props.accessibilityLabel).toBe("chat.pasted_text");
    await fireEvent.press(view.getByLabelText("chat.remove_attachment_a11y"));
    expect(onRemove).toHaveBeenCalledTimes(1);
  });
});

