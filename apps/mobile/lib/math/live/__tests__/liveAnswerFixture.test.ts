/**
 * docs/fixtures/live_answer_cases.json holds math keyboard drafts and SymPy's value for each,
 * and the API's test (test_live_answer_fixture.py) holds the chat turn to the same values:
 * the answer the composer shows while typing is the one Send verifies. A null value is a
 * draft that shows no live answer.
 */
import fixture from "../../../../../../docs/fixtures/live_answer_cases.json";
import { liveAnswer, liveValueForTest } from "@/lib/math/live/answer";

type Case = { id: string; draft: string; sympy: string | null; value: string | null; why?: string };

const CASES = (fixture as unknown as { cases: Case[] }).cases;

/** `"5/6"`, `"-4"` or `"1.41421356237310"` as a number. */
function numberOf(value: string): number {
  const [top, bottom] = value.split("/");
  return bottom === undefined ? Number(top) : Number(top) / Number(bottom);
}

function valueOf(draft: string): number | null {
  const value = liveValueForTest(draft);
  if (!value) return null;
  return value.kind === "approx" ? value.x : Number(value.r.n) / Number(value.r.d);
}

describe("live answer parity with the server", () => {
  it("has answers and refusals to check", () => {
    expect(CASES.filter((c) => c.value !== null).length).toBeGreaterThan(60);
    expect(CASES.filter((c) => c.value === null).length).toBeGreaterThan(15);
  });

  it.each(CASES.map((c) => [c.id, c] as const))("%s", (_id, c) => {
    const value = valueOf(c.draft);
    if (c.value === null) {
      expect({ draft: c.draft, value }).toEqual({ draft: c.draft, value: null });
      expect(liveAnswer(c.draft)).toBeNull();
      return;
    }
    const expected = numberOf(c.value);
    expect(value).not.toBeNull();
    const scale = Math.max(1, Math.abs(expected));
    expect({ draft: c.draft, off: Math.abs(value! - expected) <= 1e-9 * scale }).toEqual({
      draft: c.draft,
      off: true,
    });
  });
});
