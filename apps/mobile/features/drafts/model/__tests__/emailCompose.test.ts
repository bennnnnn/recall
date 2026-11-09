import {
  buildGmailAppComposeUrl,
  buildGmailComposeUrl,
  fullEmailText,
  gmailComposeCandidates,
} from "@/features/drafts/model/emailCompose";

describe("emailCompose", () => {
  const draft = {
    to: "wife@example.com",
    subject: "Thinking of You",
    body: "My love,\n\nJust thinking of you.",
  };

  it("builds full copy text", () => {
    expect(fullEmailText(draft)).toContain("To: wife@example.com");
    expect(fullEmailText(draft)).toContain("Subject: Thinking of You");
    expect(fullEmailText(draft)).toContain("My love,");
  });

  it("builds gmail web compose url", () => {
    const url = buildGmailComposeUrl(draft);
    expect(url).toContain("mail.google.com");
    expect(url).toContain("to=wife%40example.com");
    expect(url).toContain("su=Thinking%20of%20You");
  });

  it("builds gmail app compose url", () => {
    const url = buildGmailAppComposeUrl(draft);
    expect(url).toContain("googlegmail:///co");
    expect(url).toContain("subject=Thinking%20of%20You");
  });

  // URLSearchParams wrote each space as "+", which a strict URL reader (iOS's URLComponents,
  // as the Gmail app reads its link) keeps: "Thinking+of+You".
  it.each([
    ["the app link", buildGmailAppComposeUrl, "subject"],
    ["the web link", buildGmailComposeUrl, "su"],
  ])("%s reads back the same words to a strict and a form decoder", (_name, build, subjectKey) => {
    const words = { to: "a@example.com", subject: "2+2 = 4 & more", body: "Hi there,\n\nsee you at 5." };
    const url = build(words);
    const raw = (key: string) => new RegExp(`[?&]${key}=([^&]*)`).exec(url)?.[1] ?? "";
    expect(url).not.toMatch(/[?&][^=]+=[^&]*\+/);
    expect(decodeURIComponent(raw(subjectKey))).toBe(words.subject);
    expect(decodeURIComponent(raw("body"))).toBe(words.body);
    expect(new URLSearchParams(url.split("?")[1]).get(subjectKey)).toBe(words.subject);
  });

  it("orders app before web", () => {
    const urls = gmailComposeCandidates(draft);
    expect(urls[0]).toContain("googlegmail");
    expect(urls[1]).toContain("mail.google.com");
  });
});
