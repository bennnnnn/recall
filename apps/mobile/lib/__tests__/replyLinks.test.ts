/**
 * Where a reply's link opens. A name the reply marks to look up opens Maps or a search
 * while the reply streams, the address the server writes when it saves the reply with no
 * search result to go by: docs/fixtures/name_links.json holds the two to one answer (the
 * server's test is apps/api/app/tests/modules/chat/test_reply_links.py).
 */
import { nameLinkUrl, repairBrokenMarkdownLinks, replyLinkUrl } from "@/lib/markdown/replyLinks";

import fixture from "../../../../docs/fixtures/name_links.json";

type Case = { id: string; name: string; city: string; url: string };
const CASES = (fixture.cases as Case[]).map((c): [string, Case] => [c.id, c]);

describe("a name to look up (docs/fixtures/name_links.json)", () => {
  it.each(CASES)("%s: opens what the server writes", (_id, c) => {
    expect(nameLinkUrl(c.name, c.city)).toBe(c.url);
  });

  it.each(CASES)("%s: a marked link while streaming opens it too", (_id, c) => {
    expect(replyLinkUrl("check", `**${c.name}**`, c.city)).toBe(c.url);
    if (c.city) expect(replyLinkUrl(`check:${c.city}`, c.name)).toBe(c.url);
  });
});

describe("replyLinkUrl", () => {
  it("opens any other link at its own address", () => {
    expect(replyLinkUrl("https://zunicafe.com/", "Zuni Café")).toBe("https://zunicafe.com/");
    expect(replyLinkUrl("https://www.google.com/search?q=x", "x")).toBe("https://www.google.com/search?q=x");
    expect(replyLinkUrl("checkout.html", "Checkout")).toBe("checkout.html");
  });

  it("opens nothing for a mark with no name", () => {
    expect(replyLinkUrl("check", "  ")).toBe("");
  });
});

describe("repairBrokenMarkdownLinks", () => {
  it("repairs broken markdown links with dollar delimiters", () => {
    const broken = "1. [CODE Salon]$https://www.yelp.com/biz/code-salon$ — Top-rated";
    expect(repairBrokenMarkdownLinks(broken)).toBe("1. [CODE Salon](https://www.yelp.com/biz/code-salon) — Top-rated");
  });

  it("does not merge adjacent inline math spans into a broken link", () => {
    // `[0,2]$ \times $` once became `[0,2]( \times )`, leaking the `$` delimiters.
    const math = "Integrate 9 over $x \\in [0,2]$ \\times $y \\in [1,3]$:";
    expect(repairBrokenMarkdownLinks(math)).toBe(math);
  });

  it("still repairs a www. url without an explicit scheme", () => {
    expect(repairBrokenMarkdownLinks("[Google]$www.google.com$")).toBe("[Google](www.google.com)");
  });
});
