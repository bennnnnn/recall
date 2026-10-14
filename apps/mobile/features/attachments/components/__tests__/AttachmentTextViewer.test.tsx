import { render } from "@testing-library/react-native";

import { AttachmentTextViewer } from "@/features/attachments/components/AttachmentTextViewer";
import { fetchAttachmentBytes } from "@/features/attachments/model/fetchAttachmentBytes";
import { lightTheme as mockLightTheme } from "@/lib/theme";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuthToken: () => "tok",
}));
jest.mock("@/features/attachments/model/attachmentUri", () => ({
  resolveAttachmentUri: ({ attachmentId }: { attachmentId?: string }) =>
    `http://test.local/${attachmentId}`,
}));
jest.mock("@/features/attachments/model/fetchAttachmentBytes", () => ({
  fetchAttachmentBytes: jest.fn(),
}));
jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));

describe("AttachmentTextViewer", () => {
  it("shows the file text for reading", async () => {
    const encoded = new TextEncoder().encode("hello notes");
    jest.mocked(fetchAttachmentBytes).mockResolvedValueOnce(
      encoded.buffer.slice(encoded.byteOffset, encoded.byteOffset + encoded.byteLength),
    );
    const { findByText } = await render(
      <AttachmentTextViewer
        visible
        onClose={jest.fn()}
        onShare={jest.fn()}
        attachmentId="notes"
        path="/attachments/notes/file"
        fileName="notes.txt"
      />,
    );
    expect(await findByText("hello notes")).toBeTruthy();
  });

  it("cuts a long name in the middle, spins Share while it is prepared, and has a 1pt toolbar line", async () => {
    jest.mocked(fetchAttachmentBytes).mockReturnValueOnce(new Promise(() => {}));
    const { getByText, getByLabelText } = await render(
      <AttachmentTextViewer
        visible
        sharing
        onClose={jest.fn()}
        onShare={jest.fn()}
        attachmentId="notes"
        fileName="a-very-long-meeting-notes-file.md"
      />,
    );
    const title = getByText("a-very-long-meeting-notes-file.md");
    expect(title.props.ellipsizeMode).toBe("middle");
    expect(getByLabelText("preview.share").props.accessibilityState).toMatchObject({ busy: true });
    expect(title.parent).toHaveStyle({ borderBottomWidth: 1, borderBottomColor: mockLightTheme.border });
  });
});
