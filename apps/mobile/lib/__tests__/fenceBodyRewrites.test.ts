/**
 * A fence body rewrite (the email card's save) as the server writes it and the phone reads it
 * back (docs/fixtures/fence_body_rewrites.json, which the API's test_md_fence_scan.py holds to
 * `replace_first_closed_fence_body`). A draft quoting code gets a fence longer than every run
 * it holds; the phone must still draw that fence as the same card, not as prose.
 */
import cases from "../../../../docs/fixtures/fence_body_rewrites.json";
import { classifyFence } from "@/lib/fence/dispatch";
import { openerBacktickRun, replaceFirstClosedFenceBody } from "@/lib/fence/scan";
import { markdownItInstance } from "@/lib/markdown/parser";
import { parseFenceLang } from "@/lib/codeHighlight";

type Rewrite = { name: string; text: string; lang: string; body: string; expected: string };

function emailFence(text: string) {
  const token = markdownItInstance.parse(text, {}).find((t) => t.type === "fence");
  if (!token) throw new Error("no fence parsed");
  return { lang: parseFenceLang(token.info.trim()), content: token.content, markup: token.markup };
}

describe.each(cases as Rewrite[])("$name", ({ text, lang, body, expected }) => {
  it("is rewritten as the server writes it", () => {
    expect(replaceFirstClosedFenceBody(text, lang, body)).toBe(expected);
  });

  it("reads back as one fence holding the whole draft, drawn as its card", () => {
    const fence = emailFence(expected);
    expect(fence.lang).toBe(lang);
    expect(fence.content).toBe(`${body}\n`);
    const decision = classifyFence(fence.lang, fence.content.trim(), openerBacktickRun(fence.markup));
    expect(decision).toMatchObject({ kind: "rich", id: lang });
  });
});

it("still reads a run as long as the opener as a fence nested by mistake", () => {
  // The model demoed ```email inside ```email (#1261): that draft stays prose.
  expect(classifyFence("email", "To: a@b.com\n\n```email\nHi\n```", 3).kind).toBe("prose");
  expect(classifyFence("email", "To: a@b.com\n\nUse ```` here", 4).kind).toBe("prose");
  expect(openerBacktickRun(undefined)).toBe(3);
  expect(openerBacktickRun("~~~~")).toBe(3);
  expect(openerBacktickRun("`````")).toBe(5);
});
