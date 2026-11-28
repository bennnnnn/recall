/**
 * A formula's spoken label follows the app's language as it changes: the drawn formula is
 * memoized on its LaTeX, and kept "x squared" after a switch to Spanish until it remounted.
 */
import { act, render } from "@testing-library/react-native";
import * as ts from "typescript";

import { MathText } from "@/components/rich/MathText";
import es from "@/lib/i18n/es.json";
import { ENGLISH_MATH_SPEECH, readMathSpeechWords, setMathSpeechWords } from "@/lib/math/speechWords";

declare const __dirname: string;

afterEach(() => setMathSpeechWords(ENGLISH_MATH_SPEECH));

it("reads a formula again in the new language when the language changes", async () => {
  const view = await render(<MathText latex="x^2" />);
  expect(view.getByLabelText("x squared")).toBeTruthy();
  await act(async () => {
    setMathSpeechWords(readMathSpeechWords((key: string) => (es as Record<string, string>)[key] ?? key, "es"));
  });
  expect(view.getByLabelText("x al cuadrado")).toBeTruthy();
});

it("has every component that speaks maths draw again when the words change", () => {
  // A component that builds a label from the spoken words reads them where it renders; a
  // markdown rule's labels are drawn again by the piece it renders in (MarkdownPiece).
  const root = ts.sys.resolvePath(`${__dirname}/../..`);
  const speaks = /\b(spokenFormula|richTextLabel|spokenAnswerValue)\(/;
  const files = ts.sys
    .readDirectory(`${root}/components`, [".tsx"], ["**/__tests__"])
    .filter((file) => speaks.test(ts.sys.readFile(file) ?? ""))
    .map((file) => file.slice(root.length + 1));
  expect(files.length).toBeGreaterThan(5);
  const deaf = files.filter((file) => {
    const reader = file.includes("/rules/") ? "components/markdown/MarkdownPiece.tsx" : file;
    return !/useMathSpeechWords\(/.test(ts.sys.readFile(`${root}/${reader}`) ?? "");
  });
  expect(deaf).toEqual([]);
});
