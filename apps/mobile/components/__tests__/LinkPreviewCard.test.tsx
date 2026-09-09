import { render } from "@testing-library/react-native";

import { LinkPreviewCard } from "@/components/LinkPreviewCard";
import { fetchLinkPreview } from "@/lib/linkPreview";

jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/lib/linkPreview", () => ({
  fetchLinkPreview: jest.fn(),
}));
jest.mock("@/lib/linkSchemePolicy", () => ({
  openAllowedUrl: jest.fn(),
}));

const fetchPreview = fetchLinkPreview as jest.MockedFunction<typeof fetchLinkPreview>;

describe("LinkPreviewCard", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("marks a loaded preview as a link", async () => {
    fetchPreview.mockResolvedValue({
      url: "https://example.com/docs",
      title: "Example Docs",
      description: "Guide",
      domain: "example.com",
    });
    const { findByRole } = await render(
      <LinkPreviewCard url="https://example.com/docs" />,
    );
    expect(await findByRole("link", { name: "Example Docs" })).toBeOnTheScreen();
  });

  it("marks a failed preview as a link using the URL", async () => {
    fetchPreview.mockRejectedValue(new Error("offline"));
    const { findByRole } = await render(
      <LinkPreviewCard url="https://example.com/docs" />,
    );
    expect(await findByRole("link", { name: "https://example.com/docs" })).toBeOnTheScreen();
  });
});
