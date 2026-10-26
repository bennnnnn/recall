import { act, render, screen } from "@testing-library/react-native";

import { LinkPreviewCard } from "@/components/LinkPreviewCard";
import { LinkPreviewTrust } from "@/components/markdown/LinkPreviewTrust";
import { request } from "@/lib/api/client";
import { ApiRequestError } from "@/lib/api/errorBody";
import { clearLinkPreviewCache } from "@/lib/linkPreview";

jest.mock("@/lib/api/client", () => ({ request: jest.fn() }));
jest.mock("@/lib/auth", () => ({ getToken: jest.fn(async () => "token") }));
jest.mock("@/lib/linkSchemePolicy", () => ({ openAllowedUrl: jest.fn() }));

const fetchPreview = request as jest.Mock;
const LINKS = [1, 2, 3, 4].map((n) => `https://site${n}.example/page`);
/** The server lets one user have three previews loading at once (modules/link_preview/service.py). */
const SLOTS = 3;
/** Its busy refusal, with `Retry-After: 8` (modules/link_preview/api.py). */
const BUSY_MS = 8_000;

function reply() {
  return (
    <LinkPreviewTrust userText={`compare ${LINKS.join(" ")}`}>
      {LINKS.map((url) => (
        <LinkPreviewCard key={url} url={url} />
      ))}
    </LinkPreviewTrust>
  );
}

/** The server: the first three previews take slots, a fourth while they load is refused busy. */
function serveWithSlots() {
  let open = 0;
  fetchPreview.mockImplementation(async (path: string) => {
    const url = decodeURIComponent(path.split("url=")[1]);
    if (open >= SLOTS) {
      const body = JSON.stringify({ detail: { code: "link_preview_busy", message: "Too many previews loading." } });
      throw new ApiRequestError(429, body, BUSY_MS);
    }
    open += 1;
    await Promise.resolve();
    open -= 1;
    return { url, title: `Title of ${url}`, description: null, domain: new URL(url).host };
  });
}

beforeEach(() => {
  clearLinkPreviewCache();
  fetchPreview.mockReset();
  jest.restoreAllMocks();
});

it("shows a 4-link reply's busy card again after the server's wait, asking once and not before", async () => {
  const now = Date.now();
  const clock = jest.spyOn(Date, "now").mockReturnValue(now);
  serveWithSlots();

  const first = await render(reply());
  expect(await screen.findAllByText(/^Title of /)).toHaveLength(SLOTS);
  expect(screen.getByRole("link", { name: LINKS[3] })).toBeOnTheScreen();
  expect(fetchPreview).toHaveBeenCalledTimes(4);
  await act(async () => first.unmount());

  // The reply comes back into view before the wait is over: no request at all.
  clock.mockReturnValue(now + BUSY_MS - 1);
  const early = await render(reply());
  expect(await screen.findAllByText(/^Title of /)).toHaveLength(SLOTS);
  expect(screen.getByRole("link", { name: LINKS[3] })).toBeOnTheScreen();
  expect(fetchPreview).toHaveBeenCalledTimes(4);
  await act(async () => early.unmount());

  // After it: the busy link alone is asked for, once, and its card shows.
  clock.mockReturnValue(now + BUSY_MS);
  const later = await render(reply());
  expect(await screen.findByText(`Title of ${LINKS[3]}`)).toBeOnTheScreen();
  expect(screen.getAllByText(/^Title of /)).toHaveLength(4);
  expect(fetchPreview).toHaveBeenCalledTimes(5);
  await act(async () => later.unmount());

  await render(reply());
  expect(await screen.findAllByText(/^Title of /)).toHaveLength(4);
  expect(fetchPreview).toHaveBeenCalledTimes(5);
});
