import { render } from "@testing-library/react-native";

import { LinkPreviewCard } from "@/components/LinkPreviewCard";
import { LinkPreviewTrust } from "@/components/markdown/LinkPreviewTrust";
import { fetchLinkPreview } from "@/lib/linkPreview";

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
const DOCS = "https://example.com/docs";

describe("LinkPreviewCard", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("marks a loaded preview as a link", async () => {
    fetchPreview.mockResolvedValue({
      url: DOCS,
      title: "Example Docs",
      description: "Guide",
      domain: "example.com",
    });
    const { findByRole } = await render(
      <LinkPreviewTrust userText={`read ${DOCS} please`}>
        <LinkPreviewCard url={DOCS} />
      </LinkPreviewTrust>,
    );
    expect(await findByRole("link", { name: "Example Docs" })).toBeOnTheScreen();
    expect(fetchPreview).toHaveBeenCalledWith(DOCS);
  });

  it("marks a failed preview as a link using the URL", async () => {
    fetchPreview.mockRejectedValue(new Error("offline"));
    const { findByRole } = await render(
      <LinkPreviewTrust userText={DOCS}>
        <LinkPreviewCard url={DOCS} />
      </LinkPreviewTrust>,
    );
    expect(await findByRole("link", { name: DOCS })).toBeOnTheScreen();
  });

  it("previews a link from the reply's search sources", async () => {
    fetchPreview.mockResolvedValue({ url: DOCS, title: "Docs", description: null, domain: "x" });
    const { findByRole } = await render(
      <LinkPreviewTrust userText="what's new?" sources={[{ url: DOCS }]}>
        <LinkPreviewCard url={DOCS} />
      </LinkPreviewTrust>,
    );
    expect(await findByRole("link", { name: "Docs" })).toBeOnTheScreen();
  });

  it("never fetches a link the model wrote on its own", async () => {
    const exfil = "https://evil.test/p?d=dentist-tuesday";
    const { findByRole } = await render(
      <LinkPreviewTrust userText={`read ${DOCS} please`}>
        <LinkPreviewCard url={exfil} />
      </LinkPreviewTrust>,
    );
    expect(await findByRole("link", { name: exfil })).toBeOnTheScreen();
    expect(fetchPreview).not.toHaveBeenCalled();
  });

  it("fetches nothing outside a LinkPreviewTrust", async () => {
    const { findByRole } = await render(<LinkPreviewCard url={DOCS} />);
    expect(await findByRole("link", { name: DOCS })).toBeOnTheScreen();
    expect(fetchPreview).not.toHaveBeenCalled();
  });
});
