import { act, render } from "@testing-library/react-native";

import { ChatMessagePdf } from "@/features/attachments/components/ChatMessagePdf";
import { downloadChatAttachment } from "@/features/attachments/model/downloadChatAttachment";
import { serverUnreachableError } from "@/lib/api/deadline";
import { SharingUnavailableError } from "@/lib/shareUnavailable";
import { lightTheme as mockLightTheme } from "@/lib/theme";
import { alertDialog } from "@/ui/overlay/dialogs";

jest.mock("@/contexts/AuthContext", () => ({ useAuthToken: () => "tok" }));
jest.mock("@/features/attachments/hooks/useAttachmentIndexed", () => ({
  useAttachmentIndexed: () => ({ indexed: true, failed: false }),
}));
jest.mock("@/features/attachments/model/attachmentUri", () => ({
  resolveAttachmentUri: ({ attachmentId }: { attachmentId?: string }) => `https://api.test/attachments/${attachmentId}/file`,
}));
jest.mock("@/features/attachments/model/downloadChatAttachment", () => ({
  downloadChatAttachment: jest.fn(),
}));
let mockShare: (() => Promise<void>) | null = null;
jest.mock("@/features/attachments/components/AttachmentPdfViewer", () => ({
  AttachmentPdfViewer: ({ onShare }: { onShare: () => Promise<void> }) => {
    mockShare = onShare;
    return null;
  },
}));
jest.mock("@/ui/overlay/dialogs", () => ({ alertDialog: jest.fn() }));
jest.mock("@/ui/icons/Icon", () => ({ Icon: "Icon" }));
jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));
const mockWebViewProps: Record<string, unknown>[] = [];
jest.mock("@/lib/webView", () => ({
  getPreviewWebView: () => ({
    mode: "rnc",
    Component: (props: Record<string, unknown>) => {
      mockWebViewProps.push(props);
      const { View: MockView } = jest.requireActual<typeof import("react-native")>("react-native");
      return <MockView testID="pdf-webview" />;
    },
  }),
}));

// A sent PDF showed its card, then a second bubble with page 1 drawn: the same file twice,
// read as another message (2026-11-07). The card alone names it and opens the viewer.
it("draws the file's card and no page picture under it", async () => {
  const { getByText, queryByTestId } = await render(
    <ChatMessagePdf attachmentId="doc" fileName="lease-notes.pdf" />,
  );
  expect(getByText("lease-notes.pdf")).toBeOnTheScreen();
  expect(queryByTestId("pdf-webview", { includeHiddenElements: true })).toBeNull();
  expect(mockWebViewProps).toHaveLength(0);
});

it("gives a screen reader one way in: the named card", async () => {
  const { getAllByRole } = await render(<ChatMessagePdf attachmentId="doc" fileName="lease-notes.pdf" />);
  expect(getAllByRole("button").map((button) => button.props.accessibilityLabel)).toEqual([
    "chat.pdf_open_a11y",
  ]);
});

// The viewer's Share showed the failure's English as it came, in every language.
it.each([
  ["no answer", serverUnreachableError(), "chat.error_unreachable"],
  ["no connection", new TypeError("Network request failed"), "chat.error_unreachable"],
  ["a file the phone could not open", new Error("Could not open this attachment."), "chat.pdf_export_failed"],
  ["a build that cannot share files", new SharingUnavailableError(), "common.share_needs_update"],
])("words a share that failed with %s in the phone's language", async (_label, failure, key) => {
  jest.mocked(downloadChatAttachment).mockRejectedValueOnce(failure);
  await render(<ChatMessagePdf attachmentId="doc" fileName="lease-notes.pdf" />);
  await act(async () => { await mockShare?.(); });
  expect(alertDialog).toHaveBeenLastCalledWith({ title: "common.download_failed", message: key });
});
