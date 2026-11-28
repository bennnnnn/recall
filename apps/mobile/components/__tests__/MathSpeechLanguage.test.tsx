/**
 * A formula's spoken label follows the app's language as it changes: the drawn formula is
 * memoized on its LaTeX, and kept "x squared" after a switch to Spanish until it remounted.
 */
import { act, render } from "@testing-library/react-native";

import { MathText } from "@/components/rich/MathText";
import es from "@/lib/i18n/es.json";
import { ENGLISH_MATH_SPEECH, readMathSpeechWords, setMathSpeechWords } from "@/lib/math/speechWords";

afterEach(() => setMathSpeechWords(ENGLISH_MATH_SPEECH));

it("reads a formula again in the new language when the language changes", async () => {
  const view = await render(<MathText latex="x^2" />);
  expect(view.getByLabelText("x squared")).toBeTruthy();
  await act(async () => {
    setMathSpeechWords(readMathSpeechWords((key: string) => (es as Record<string, string>)[key] ?? key, "es"));
  });
  expect(view.getByLabelText("x al cuadrado")).toBeTruthy();
});
