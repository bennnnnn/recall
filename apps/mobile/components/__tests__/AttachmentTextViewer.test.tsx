import { render } from "@testing-library/react-native";

import { AttachmentTextViewer } from "@/components/AttachmentTextViewer";
import { fetchAttachmentBytes } from "@/lib/fetchAttachmentBytes";
import { lightTheme as mockLightTheme } from "@/lib/theme";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuthToken: () => "tok",
}));
jest.mock("@/lib/attachmentUri", () => ({
  resolveAttachmentUri: ({ attachmentId }: { attachmentId?: string }) =>
    `http://test.local/${attachmentId}`,
}));
jest.mock("@/lib/fetchAttachmentBytes", () => ({
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
});
