/**
 * A PDF ends as a text share does, and its link is one a reader can tap: the footer is a
 * markdown link through the real print renderer. A user's code fence left open no longer
 * holds the rest of the PDF, its footer included, as code.
 */
import { exportConversationAsPdf } from "@/features/chat/model/exportMessagePdf";
import { printHtmlToSharedPdf } from "@/features/chat/model/exportPdf";
import type { Message } from "@/lib/api";

jest.mock("@/lib/i18n", () => ({
  __esModule: true,
  default: { t: (key: string, values?: Record<string, string>) => (values?.url ? `get ${values.url}` : key) },
}));
jest.mock("@/lib/config", () => ({ config: { shareUrl: "https://example.com/get" } }));
jest.mock("@/features/chat/model/exportPdf", () => ({ printHtmlToSharedPdf: jest.fn(async () => undefined) }));

async function printed(messages: Message[]): Promise<string> {
  await exportConversationAsPdf("Chat", messages);
  return String(jest.mocked(printHtmlToSharedPdf).mock.calls.at(-1)?.[0] ?? "");
}

it("links the footer's get-the-app line", async () => {
  const html = await printed([{ id: "a1", role: "assistant", content: "Paris." }] as Message[]);
  expect(html).toContain('href="https://example.com/get?ref=share"');
  expect(html).toContain("share.footer_from");
});

it("closes a fence the user left open, so the footer prints as text", async () => {
  const html = await printed([
    { id: "u1", role: "user", content: "```py\nprint(1)" },
    { id: "a1", role: "assistant", content: "That prints 1." },
  ] as Message[]);
  const code = html.slice(html.indexOf("<pre"), html.indexOf("</pre>"));
  expect(code).toContain("print(1)");
  expect(code).not.toContain("That prints 1.");
  expect(code).not.toContain("share.footer_from");
  expect(html).toContain('href="https://example.com/get?ref=share"');
});

it("closes the user's open fence before their photo's label, which prints as text", async () => {
  const html = await printed([
    { id: "u1", role: "user", content: "```py\nprint(1)\n[Image: /attachments/a1/photo.jpg]" },
    { id: "a1", role: "assistant", content: "That prints 1." },
  ] as Message[]);
  const code = html.slice(html.indexOf("<pre"), html.indexOf("</pre>"));
  expect(code).toContain("print(1)");
  expect(code).not.toContain("share.attachment_photo");
  expect(html).toContain("share.attachment_photo");
});
