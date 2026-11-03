/**
 * Real chemistry replies from the server (docs/fixtures/chemistry_replies.json), read the way
 * the app reads them. The server's own test proves it still writes exactly these replies.
 */
import { CHEMISTRY_ANSWER_NOTATION, splitAnswerNotation } from "@/lib/answerNotation";
import { parseChemistryScene } from "@/lib/chemistry/scene";
import { markdownToCopyText, markdownToSpeechText } from "@/lib/markdown/plain";
import { preprocessMarkdown } from "@/lib/markdown/preprocess";

import fixture from "../../../../docs/fixtures/chemistry_replies.json";

type Contract = {
  answer_notation: string;
  replies: Record<string, { question: string; reply: string }>;
};

const contract: Contract = fixture;
const replies = Object.entries(contract.replies);

function fenceBodies(markdown: string, lang: string): string[] {
  const bodies: string[] = [];
  const open = "```" + lang + "\n";
  let from = 0;
  while (true) {
    const start = markdown.indexOf(open, from);
    if (start < 0) return bodies;
    const end = markdown.indexOf("\n```", start + open.length);
    bodies.push(markdown.slice(start + open.length, end));
    from = end + 4;
  }
}

describe("server chemistry replies", () => {
  it("use the notation header the app strips", () => {
    expect(CHEMISTRY_ANSWER_NOTATION).toBe(contract.answer_notation);
  });

  // One quantity's value is maths, as every subject's card is (n(\mathrm{H₂O}) = 2.0\,\mathrm{mol});
  // an equation, a name or a list is chemistry text under the notation header.
  it.each(replies)("%s: every answer fence is maths or chemistry notation with a visible answer", (_name, entry) => {
    const answers = fenceBodies(entry.reply, "answer");
    expect(answers.length).toBeGreaterThan(0);
    for (const raw of answers) {
      const { notation, body } = splitAnswerNotation(raw);
      expect(notation === "chemistry" || /\\mathrm\{/.test(body)).toBe(true);
      expect(body).not.toContain("notation");
      expect(body.length).toBeGreaterThan(0);
    }
  });

  it.each(replies)("%s: every scene is one the app can draw", (_name, entry) => {
    for (const raw of fenceBodies(entry.reply, "chem_scene")) {
      expect(parseChemistryScene(raw)).not.toBeNull();
    }
  });

  it.each(replies)("%s: copy and read-aloud carry the answer, not the plumbing", (_name, entry) => {
    const [answer] = fenceBodies(entry.reply, "answer");
    const { notation, body } = splitAnswerNotation(answer!);
    // Chemistry text is read as written; a maths card by its value, never its TeX.
    const visible = notation === "chemistry" ? body.split("\n")[0]! : /\d+(?:\.\d+)?(?!.*\d)/.exec(body)![0];
    for (const text of [markdownToCopyText(entry.reply), markdownToSpeechText(entry.reply)]) {
      expect(text).toContain(visible);
      expect(text).not.toContain("\\mathrm");
      expect(text).not.toContain("notation");
      expect(text).not.toContain('"kind"');
      expect(text).not.toContain("```");
    }
  });

  it.each(replies)("%s: the markdown pipeline leaves the fences it draws", (_name, entry) => {
    const out = preprocessMarkdown(entry.reply);
    expect(fenceBodies(out, "answer")).toHaveLength(fenceBodies(entry.reply, "answer").length);
    expect(fenceBodies(out, "chem_scene")).toEqual(fenceBodies(entry.reply, "chem_scene"));
  });

  it.each(replies)("%s: as sent, the card is checked and the marker is never read", (_name, entry) => {
    // The server marks a direct reply's cards when it sends them.
    const sent = entry.reply.replaceAll("```answer\n", "```answer\nverified: true\n");
    for (const raw of fenceBodies(preprocessMarkdown(sent), "answer")) {
      const parsed = splitAnswerNotation(raw);
      expect(parsed.verified).toBe(true);
      expect(parsed.notation === "chemistry" || /\\mathrm\{/.test(parsed.body)).toBe(true);
    }
    for (const text of [markdownToCopyText(sent), markdownToSpeechText(sent)]) {
      expect(text).not.toContain("verified");
      expect(text).not.toContain("notation");
    }
  });
});
