import {
  answersFromMessage,
  canSubmitClarify,
  clarifyMessage,
  clarifyText,
  parseClarifyCard,
  type ClarifyCard,
} from "@/lib/clarify/clarifyCard";

// The integrals card from docs/clarify.md.
const INTEGRALS = JSON.stringify({
  when: "first",
  questions: [
    {
      id: "level",
      label: "Studied it before",
      question: "Have you studied integrals before?",
      options: ["No, never", "A little", "Yes, I'm revising"],
      multi: false,
    },
    {
      id: "goal",
      label: "What it's for",
      question: "What do you need it for?",
      options: ["An exam", "A class", "Curiosity"],
      multi: false,
    },
  ],
});

function card(content = INTEGRALS): ClarifyCard {
  const parsed = parseClarifyCard(content);
  if (!parsed) throw new Error("expected a card");
  return parsed;
}

describe("parseClarifyCard", () => {
  it("reads the card the server keeps", () => {
    const parsed = card();
    expect(parsed.when).toBe("first");
    expect(parsed.questions.map((q) => q.label)).toEqual(["Studied it before", "What it's for"]);
    expect(parsed.questions[0]!.options).toEqual(["No, never", "A little", "Yes, I'm revising"]);
    expect(parsed.questions[0]!.multi).toBe(false);
  });

  it("fills a missing id or label and reads an unknown when as first", () => {
    const parsed = card(
      JSON.stringify({
        when: "later",
        questions: [{ question: "Which OS?", options: ["iOS", "Android"] }],
      }),
    );
    expect(parsed.when).toBe("first");
    expect(parsed.questions[0]).toMatchObject({ id: "q1", label: "Which OS?", multi: false });
  });

  it("keeps an after card", () => {
    const parsed = card(
      JSON.stringify({ when: "after", questions: [{ label: "OS", question: "Which?", options: ["a", "b"] }] }),
    );
    expect(parsed.when).toBe("after");
  });

  it("drops blank and repeated options, and gives repeated ids new ones", () => {
    const parsed = card(
      JSON.stringify({
        questions: [
          { id: "x", label: "A", question: "A?", options: ["Yes", " yes ", "", "No"] },
          { id: "x", label: "B", question: "B?", options: ["1", "2"] },
        ],
      }),
    );
    expect(parsed.questions[0]!.options).toEqual(["Yes", "No"]);
    expect(parsed.questions.map((q) => q.id)).toEqual(["q1", "q2"]);
  });

  it.each([
    ["not JSON", "Have you studied integrals before?"],
    ["no questions", JSON.stringify({ when: "first", questions: [] })],
    [
      "four questions",
      JSON.stringify({
        questions: [1, 2, 3, 4].map((n) => ({ label: `L${n}`, question: `Q${n}?`, options: ["a", "b"] })),
      }),
    ],
    ["one option", JSON.stringify({ questions: [{ label: "L", question: "Q?", options: ["a"] }] })],
    [
      "five options",
      JSON.stringify({ questions: [{ label: "L", question: "Q?", options: ["a", "b", "c", "d", "e"] }] }),
    ],
    ["no question text", JSON.stringify({ questions: [{ label: "L", options: ["a", "b"] }] })],
    ["a question that is not an object", JSON.stringify({ questions: ["Q?"] })],
  ])("refuses %s", (_name, content) => {
    expect(parseClarifyCard(content)).toBeNull();
  });
});

describe("clarifyMessage", () => {
  it("writes one Label: pick line per question, as the server reads it", () => {
    const parsed = card();
    const message = clarifyMessage(parsed, {
      level: { picked: ["No, never"], other: null },
      goal: { picked: ["An exam"], other: null },
    });
    expect(message).toBe("Studied it before: No, never\nWhat it's for: An exam");
  });

  it("joins several picks in the card's order, then the typed text on one line", () => {
    const parsed = card(
      JSON.stringify({
        questions: [
          { id: "use", label: "Used for", question: "What for?", options: ["Games", "Work", "Study"], multi: true },
        ],
      }),
    );
    const message = clarifyMessage(parsed, {
      use: { picked: ["Study", "Games"], other: "  video\n editing " },
    });
    expect(message).toBe("Used for: Games, Study, video editing");
  });

  it("uses Other… text alone when nothing else is picked", () => {
    const parsed = card();
    const message = clarifyMessage(parsed, {
      level: { picked: [], other: "I took calculus years ago" },
      goal: { picked: ["Curiosity"], other: null },
    });
    expect(message).toBe("Studied it before: I took calculus years ago\nWhat it's for: Curiosity");
  });
});

describe("canSubmitClarify", () => {
  it("needs an answer for every question", () => {
    const parsed = card();
    expect(canSubmitClarify(parsed, {})).toBe(false);
    expect(canSubmitClarify(parsed, { level: { picked: ["A little"], other: null } })).toBe(false);
    expect(
      canSubmitClarify(parsed, {
        level: { picked: ["A little"], other: null },
        goal: { picked: [], other: "   " },
      }),
    ).toBe(false);
    expect(
      canSubmitClarify(parsed, {
        level: { picked: ["A little"], other: null },
        goal: { picked: [], other: "A job interview" },
      }),
    ).toBe(true);
  });
});

describe("answersFromMessage", () => {
  it("reads the sent picks back onto the card", () => {
    const parsed = card();
    expect(answersFromMessage(parsed, "Studied it before: Yes, I'm revising\nWhat it's for: An exam")).toEqual({
      level: { picked: ["Yes, I'm revising"], other: null },
      goal: { picked: ["An exam"], other: null },
    });
  });

  it("reads a typed answer as Other…", () => {
    const parsed = card();
    expect(answersFromMessage(parsed, "studied it before: a long time ago\nWhat it's for: A class")).toEqual({
      level: { picked: [], other: "a long time ago" },
      goal: { picked: ["A class"], other: null },
    });
  });

  it("reads several picks back, an option with a comma in it too, then the typed rest", () => {
    const parsed = card(
      JSON.stringify({
        questions: [
          {
            id: "pick",
            label: "Picked",
            question: "Which?",
            options: ["Yes, I'm revising", "Yes", "Maybe"],
            multi: true,
          },
        ],
      }),
    );
    expect(answersFromMessage(parsed, "Picked: Yes, I'm revising, Maybe, something else")).toEqual({
      pick: { picked: ["Yes, I'm revising", "Maybe"], other: "something else" },
    });
  });

  it.each([
    ["Skip", "Just answer"],
    ["a new question", "What about derivatives?"],
    ["a line that names no question", "Studied it before: No, never\nBudget: $500"],
    ["an empty value", "Studied it before:"],
  ])("is null for %s", (_name, message) => {
    expect(answersFromMessage(card(), message)).toBeNull();
  });

  it("round-trips what Submit sends", () => {
    const parsed = card();
    const answers = {
      level: { picked: ["A little"], other: null },
      goal: { picked: [], other: "A job interview" },
    };
    expect(answersFromMessage(parsed, clarifyMessage(parsed, answers))).toEqual(answers);
  });
});

describe("clarifyText", () => {
  it("is each question with its choices", () => {
    expect(clarifyText(card())).toBe(
      "Have you studied integrals before? (No, never / A little / Yes, I'm revising)\n" +
        "What do you need it for? (An exam / A class / Curiosity)",
    );
  });
});
