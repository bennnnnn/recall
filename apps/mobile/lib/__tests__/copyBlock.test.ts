import {
  isAnswerLang,
  draftFenceProseText,
  looksLikeCode,
  looksLikeExplicitDraftContent,
  looksLikeMathAnswer,
  shouldRenderAsCopyBlock,
  shouldRenderAsCodeBlock,
  shouldRenderAsPlainProseFence,
} from "@/lib/copyBlock";
import { classifyFence, classifyOpenFencePreview } from "@/lib/fence/dispatch";
import { isSendableFenceLang } from "@/lib/fence/registry";
import { unwrapNonCodeFences } from "@/lib/markdown/preprocessTables";

const previewsAsAnswer = (lang: string, body: string) => classifyOpenFencePreview(lang, body) === "answer";
const previewsAsMath = (lang: string, body: string) => classifyOpenFencePreview(lang, body) === "math";

describe("copyBlock heuristics", () => {
  it("knows the tags of text to send from the fence registry", () => {
    expect(isSendableFenceLang("copy")).toBe(true);
    expect(isSendableFenceLang("EMAIL")).toBe(true);
    expect(isSendableFenceLang("linkedin")).toBe(true);
    expect(isSendableFenceLang("text")).toBe(false);
    expect(isSendableFenceLang("python")).toBe(false);
  });

  it("detects source code vs prose", () => {
    expect(looksLikeCode("def hello():\n    print('hi')")).toBe(true);
    expect(looksLikeCode("let total = 2;")).toBe(true);
    expect(looksLikeCode("Hi team,\n\nThanks for the update.\n\nBest,")).toBe(false);
  });

  it("routes email drafts to copy block", () => {
    const draft = `Subject: Follow up\n\nHi Alex,\n\nJust checking in.\n\nThanks,\nSam`;
    expect(shouldRenderAsCopyBlock("email", draft)).toBe(true);
    expect(shouldRenderAsCodeBlock("email", draft)).toBe(false);
  });

  it("routes python fences to code block", () => {
    const code = "def add(a, b):\n    return a + b";
    expect(shouldRenderAsCodeBlock("python", code)).toBe(true);
    expect(shouldRenderAsCopyBlock("python", code)).toBe(false);
  });

  // The tag decides, in every language. English phrase lists ("As a …", "Hi … Thanks,")
  // made an English draft a card and the same draft in Spanish plain text, and read any
  // untagged body over 100 characters as advice, so a code snippet unwrapped into prose.
  it("trusts a ```copy tag as a draft in any language, and reads no untagged prose as one", () => {
    const advice =
      "As a software engineer, Python is a solid choice for prototyping. JavaScript is great for the frontend.";
    expect(shouldRenderAsCopyBlock("copy", advice)).toBe(true);
    const english = "Hi Ana,\n\nCould I take Friday off? I have an appointment.\n\nThanks,\nBini";
    const spanish = "Hola Ana,\n\n¿Puedo tomarme el viernes libre? Tengo una cita.\n\nGracias,\nBini";
    for (const draft of [english, spanish, advice]) {
      expect(shouldRenderAsCopyBlock("", draft)).toBe(false);
      expect(shouldRenderAsPlainProseFence("", draft)).toBe(true);
      expect(classifyOpenFencePreview("", draft)).toBe("prose");
    }
  });

  it("keeps an untagged code snippet a code block, however long", () => {
    const code =
      "function add(a, b) {\n  return a + b;\n}\nconst total = add(1, 2);\nconsole.log(total); // prints 3 as expected\n";
    expect(code.length).toBeGreaterThan(100);
    expect(looksLikeCode(code)).toBe(true);
    expect(unwrapNonCodeFences(`\`\`\`\n${code}\`\`\``)).toContain("```");
    const trace = "Traceback (most recent call last):\n  File \"app.py\", line 42, in profile\n    user_id = session[\"user_id\"]\nKeyError: 'user_id'";
    expect(unwrapNonCodeFences(`\`\`\`text\n${trace}\n\`\`\``)).toContain("```text");
  });

  it("keeps a draft that opens on a [Name] placeholder a draft", () => {
    const bio =
      "[Name] is a 5th-grade teacher in Seattle with eight years of classroom experience. Outside school, she hikes.";
    expect(looksLikeCode(bio)).toBe(false);
    expect(classifyFence("copy", bio).kind).toBe("copy");
    expect(looksLikeCode('[{"x": 1}, {"x": 2}]')).toBe(true);
  });

  it("rejects the leaked screenshot instructions from a draft card", () => {
    const leaked =
      "fence!\n(Or paste their number if SMS and you want it formatted for texting.)";
    expect(looksLikeExplicitDraftContent(leaked)).toBe(false);
    expect(shouldRenderAsCopyBlock("copy", leaked)).toBe(false);
    expect(draftFenceProseText(leaked)).not.toContain("fence!");
    expect(draftFenceProseText(leaked)).toContain("paste their number");
  });

  it("rejects a nested ```sms example that leaked into an email fence", () => {
    const leaked =
      "to reschedule a meeting or ```sms to confirm plans)\n## phases with numbered tasks";
    expect(looksLikeExplicitDraftContent(leaked)).toBe(false);
    expect(shouldRenderAsCopyBlock("email", leaked)).toBe(false);
  });

  it.each([
    "¡Feliz cumpleaños! Espero que tengas un día maravilloso lleno de alegría.",
    "መልካም ልደት! ዛሬ በደስታ እና በፍቅር የተሞላ ቀን እንዲሆንልህ እመኛለሁ።",
    "祝你生日快乐！愿你今天充满欢笑，也愿新的一年带给你平安和惊喜。",
  ])("accepts explicit multilingual copy as a real draft: %s", (draft) => {
    expect(looksLikeExplicitDraftContent(draft)).toBe(true);
    expect(shouldRenderAsCopyBlock("copy", draft)).toBe(true);
  });

  // An aside in brackets or a sentence opening on "Class" / "Update" read as code,
  // and the draft lost its card: the email showed as plain text, no Copy, no Gmail.
  it.each([
    [
      "email",
      "Subject: Friday off\n\nHi Sara,\n\nCould I take Friday (Oct 24) off for a family event?\n\nThanks,\nBini",
    ],
    [
      "copy",
      "Dear Hiring Manager,\n\nI'm applying for the nurse position (job #4412) at your hospital.\n\nSincerely,\nBini",
    ],
    ["instagram", "Golden hour at the beach (no filter needed).\n\n#sunset #beach"],
    ["message", "Hi Ms. Tigist,\nClass starts at 9 tomorrow, but I'll pick Abel up at 11:30.\nThanks, Bini"],
    ["message", "Hey team,\nUpdate the on-call wiki before Friday please.\nThanks!"],
    [
      "email",
      "Subject: Missing package\n\nHi,\n\nPackage 4412 was marked delivered but never arrived.\n\nThanks,\nBini",
    ],
  ])("keeps a %s draft with ordinary prose a draft card", (lang, draft) => {
    expect(looksLikeCode(draft)).toBe(false);
    expect(looksLikeExplicitDraftContent(draft)).toBe(true);
    expect(classifyFence(lang, draft).kind).not.toBe("prose");
  });

  it.each([
    "foo(bar);\nbaz()",
    "import os\nprint(os.getcwd())",
    "class Greeter:\n    pass",
    "SELECT name FROM users\nWHERE id = 1",
    "<View>\n  <Text>Hi</Text>\n</View>",
    "result = compute(a, b)\nshow(result)",
  ])("still reads source code as code: %j", (code) => {
    expect(looksLikeCode(code)).toBe(true);
  });

  it("keeps a real message that naturally starts with 'Let me know if'", () => {
    const draft = "Let me know if you can make dinner at 7. I hope you can join us!";
    expect(looksLikeCode(draft)).toBe(false);
    expect(looksLikeExplicitDraftContent(draft)).toBe(true);
    expect(shouldRenderAsCopyBlock("copy", draft)).toBe(true);
  });

  it("does not treat a prose expression like 2 + Y as a final-answer card", () => {
    expect(looksLikeMathAnswer("2 + Y")).toBe(false);
    expect(looksLikeMathAnswer("Y")).toBe(false);
    expect(looksLikeMathAnswer("$Y$")).toBe(false);
  });

  it("treats short numeric finals as math answers, not Copy", () => {
    expect(looksLikeMathAnswer("120")).toBe(true);
    expect(looksLikeMathAnswer("$x = 3$")).toBe(true);
    expect(looksLikeMathAnswer("\\boxed{120}")).toBe(true);
    expect(looksLikeMathAnswer("x = 2")).toBe(true);
    expect(looksLikeMathAnswer("0! = 1")).toBe(false);
    expect(isAnswerLang("answer")).toBe(true);
    expect(shouldRenderAsCopyBlock("copy", "120")).toBe(false);
    expect(shouldRenderAsCopyBlock("answer", "120")).toBe(false);
  });

  it("BUG FIX regression: treats a bare simplified algebraic expression (no =) as a math answer, not Copy", () => {
    // Reported live (screenshot): a simplified result like "2c^2" has no "="
    // and isn't a bare number, so it fell through every existing branch of
    // looksLikeMathAnswer and landed on the generic CodeBlock fallback,
    // which shows a "Copy" button — a final answer must never show Copy.
    expect(looksLikeMathAnswer("2c^2")).toBe(true);
    expect(looksLikeMathAnswer("x^2 - 4")).toBe(true);
    expect(looksLikeMathAnswer("\\frac{1}{2}")).toBe(true);
    expect(looksLikeMathAnswer("√2")).toBe(true);
    expect(shouldRenderAsCopyBlock("copy", "2c^2")).toBe(false);
    expect(shouldRenderAsCodeBlock("copy", "2c^2")).toBe(false);
  });

  it("BUG FIX regression: treats a multi-solution final (both quadratic roots, optionally $-wrapped) as a math answer, not Copy/Code", () => {
    // Models emit both roots as the final answer, often with each term in
    // $...$ and sometimes mis-tagged ```copy. The literal `$` chars (and the
    // `=` + "or") used to fail every detector and drop onto the fallback
    // CodeBlock — raw `$`, a Copy button, syntax-highlighted numbers. A final
    // answer must route to AnswerBlock instead.
    expect(looksLikeMathAnswer("x = 2 or x = -2")).toBe(true);
    expect(looksLikeMathAnswer("$x = 2$ or $x = -2$")).toBe(true);
    expect(looksLikeMathAnswer("x = 2 and x = -2")).toBe(true);
    expect(looksLikeMathAnswer("x = 2, x = -2")).toBe(true);
    expect(shouldRenderAsCopyBlock("copy", "$x = 2$ or $x = -2$")).toBe(false);
    expect(shouldRenderAsCodeBlock("copy", "$x = 2$ or $x = -2$")).toBe(false);
  });

  it("does not misclassify plain prose as a math answer", () => {
    // MATH_ANSWER_CHARS_RE alone would allow "the answer is" (letters +
    // spaces) — the digit/operator + two-real-words guards must reject it.
    expect(looksLikeMathAnswer("the answer")).toBe(false);
    expect(looksLikeMathAnswer("Great job")).toBe(false);
    expect(looksLikeMathAnswer("Copy")).toBe(false);
  });

  it("BUG FIX regression: open ```answer fences preview as the card, never a code card", () => {
    // Live: the final box flashed `x = -2 \quad \text{or} \quad x = 2` in a
    // CodeBlock (lang badge "answer") until the fence closed. Any ```answer
    // previews as the card (the check waits for the server's mark and the
    // settled reply); a soft fence that looks like an answer previews as math.
    const roots = String.raw`x = -2 \quad \text{or} \quad x = 2`;
    expect(previewsAsAnswer("answer", `verified: true\n${roots}`)).toBe(true);
    expect(previewsAsAnswer("answer", roots)).toBe(true);
    expect(previewsAsAnswer("python", "print(1)")).toBe(false);
    expect(previewsAsAnswer("python", "x = 2")).toBe(false);
    expect(previewsAsAnswer("", "x = 2 or x = -2")).toBe(false);
    expect(previewsAsMath("", "x = 2 or x = -2")).toBe(true);
  });

  it("BUG FIX regression: open ```math fences preview as math, not a code card", () => {
    expect(previewsAsMath("math", String.raw`\frac{1}{2}`)).toBe(true);
    expect(previewsAsMath("python", "print(1)")).toBe(false);
    expect(previewsAsMath("", String.raw`x^2 = 4`)).toBe(true);
  });

  it("BUG FIX regression: open ```math is never previewed as AnswerBlock mid-stream", () => {
    // Half-streamed display math looks like a bare expression (no "=" yet)
    // which looksLikeMathAnswer matches. Settled renderFence already guards
    // with isMathDiagramLang; the open-tail path must share that rule.
    expect(
      classifyOpenFencePreview("math", String.raw`\frac{x^2}{2}`),
    ).toBe("math");
    expect(
      previewsAsAnswer("math", String.raw`\frac{x^2}{2}`),
    ).toBe(false);
  });

  it("BUG FIX regression: open ```latex/```tex preview as math, not a code card", () => {
    expect(classifyOpenFencePreview("latex", String.raw`\frac{x^2}{2}`)).toBe("math");
    expect(classifyOpenFencePreview("tex", "x^2 = 8")).toBe("math");
    expect(previewsAsMath("latex", String.raw`\frac{x^2}{2}`)).toBe(true);
  });

  it("BUG FIX regression: open ```geometry/```graph preview as diagram, not JSON CodeBlock", () => {
    expect(classifyOpenFencePreview("geometry", '{"type":"square"')).toBe("placeholder");
    expect(classifyOpenFencePreview("graph", '{"type":"function"')).toBe("placeholder");
  });

  it("does not flash a gray diagram box for an open ```molecule3d tail", () => {
    expect(classifyOpenFencePreview("molecule3d", "     RDKit")).toBe("hide");
    expect(classifyOpenFencePreview("mol3d", "")).toBe("hide");
  });
});
