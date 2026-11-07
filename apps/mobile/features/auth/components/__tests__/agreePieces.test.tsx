import { agreePieces } from "@/features/auth/components/AgreeLine";
import en from "@/lib/i18n/en.json";
import tr from "@/lib/i18n/tr.json";

/** The line as it reads on screen: a space only where a piece is spaced. */
const shown = (sentence: string) =>
  agreePieces(sentence)
    .map((piece) => (piece.spaced ? " " : "") + piece.text)
    .join("");

it("reads as the translated sentence, links included", () => {
  const line = en["login.agree_line"].replace(/<\/?(terms|privacy)>/g, "");
  expect(shown(en["login.agree_line"])).toBe(line);
});

it('keeps a suffix glued to its link (review of #2314: Turkish read "Koşullar \'ı")', () => {
  const line = tr["login.agree_line"].replace(/<\/?(terms|privacy)>/g, "");
  expect(shown(tr["login.agree_line"])).toBe(line);
  expect(shown(tr["login.agree_line"])).toContain("Koşullar'ı");
});

it("marks the two links", () => {
  const links = agreePieces(en["login.agree_line"]).filter(
    (piece) => piece.link,
  );
  expect(links.map((piece) => piece.link)).toEqual(["terms", "privacy"]);
});
