import {
  askedLine,
  isAnswerHeading,
  isAnswerValue,
  isSolutionHeading,
  isWorkedReply,
  lawHeading,
  splitWorkoutNote,
  workoutHeading,
} from "@/lib/markdown/workoutSection";

describe("splitWorkoutNote", () => {
  it.each([
    ["$2x = 8$ — subtract 3", { state: "$2x = 8$", note: "subtract 3" }],
    ["$a — b$ — a dash inside math stays math", { state: "$a — b$", note: "a dash inside math stays math" }],
    ["Every step checks out.", { state: "Every step checks out.", note: null }],
    ["$x > 0$ — domain for $x$", { state: "$x > 0$", note: "domain for $x$" }],
  ])("%s", (line, expected) => {
    expect(splitWorkoutNote(line)).toEqual(expected);
  });
});

describe("askedLine", () => {
  it.each([
    ["$v$ — speed", "$v$ (speed)"],
    ["(a) $d$ — displacement of the car (due East)", "(a) $d$ (displacement of the car (due East))"],
    ["$v$ (speed)", "$v$ (speed)"],
    ["$a — b$", "$a — b$"],
    ["$t$", "$t$"],
  ])("%s", (line, expected) => {
    expect(askedLine(line)).toBe(expected);
  });
});

describe("isSolutionHeading", () => {
  it.each([
    ["Solution", true],
    ["Solution:", true],
    [" Solution ", true],
    ["Solutions", false],
    ["Formula", false],
  ])("%s", (text, expected) => {
    expect(isSolutionHeading(text)).toBe(expected);
  });
});

describe("workoutHeading", () => {
  it.each([
    ["Given", "Given"],
    ["Required", "Required"],
    // A reply written before November 2026 headed what is asked "Find".
    ["Find", "Find"],
    ["Steps:", "Steps"],
    ["Substitution", "Substitution"],
    ["Diagram", null],
    ["1. Subtract 3", null],
    ["Answer (a)", "Answer (a)"],
    ["Answer (z)", null],
  ])("%s", (text, expected) => {
    expect(workoutHeading(text)).toBe(expected);
  });

  it.each([
    ["**Given**  \n$v = 25$", true],
    ["**Required**  \n$t$", true],
    ["**Find**  \n$t$", true],
    ["**Requirements**  \nNode 18", false],
    ["What is required to find $t$?", false],
  ])("reads %j as worked: %s", (text, expected) => {
    expect(isWorkedReply(text)).toBe(expected);
  });

  it("reads one part's answer as an answer", () => {
    expect(isAnswerHeading("Answer")).toBe(true);
    expect(isAnswerHeading("Answer (b)")).toBe(true);
    expect(isAnswerHeading("Answers")).toBe(false);
  });
});

describe("lawHeading", () => {
  it.each([
    ["Constant acceleration", "$v = u + at$", "Constant acceleration"],
    ["Newton's second law", "$F = ma$ — net force", "Newton's second law"],
    // Not a heading over maths: a sentence, a numbered move, a part, or no maths below.
    ["Now solve for a.", "$a = 2$", null],
    ["1. Subtract 4 from both sides", "$2x = 8$", null],
    ["(a) Time in the air", "$t = 2$", null],
    ["Constant acceleration", "The car speeds up evenly.", null],
    ["Ideal mechanical advantage of a wheel and axle", "$\mathrm{IMA} = R/r$", "Ideal mechanical advantage of a wheel and axle"],
    ["A heading that runs far too long to be the name of one law", "$x$", null],
  ])("%s over %s", (text, firstLine, expected) => {
    expect(lawHeading(text, firstLine)).toBe(expected);
  });
});

describe("isAnswerValue", () => {
  // The textbook run (2026-11-13): a graph's answer in words was drawn in the answer box.
  // A sentence its maths only illustrates: no relation, words after the maths.
  it.each([
    "A line from $(-3, -5)$ to $(3, 7)$ — slope $2$, $y$-intercept $1$.",
    "Slope $2$, $y$-intercept $1$, a line from $(-3, -5)$ to $(3, 7)$.",
    "$(0, 1)$ is where the line crosses the $y$-axis",
    "The line has slope $2$ and passes through $(0, 1)$.",
    "Die Gerade hat die Steigung $2$ und schneidet die $y$-Achse bei $(0, 1)$.",
    "Only the positive root counts.",
  ])("reads %s as a sentence", (line) => {
    expect(isAnswerValue(line)).toBe(false);
  });

  it.each([
    "$c = 15\\ \\text{cm}$",
    "Total area: $A = 24$",
    "$5°$ from the normal",
    "Approximately $4.2$ s",
    "Speed = 4 m/s",
    "Average speed = total distance / total time = 4 m/s",
    "Paris",
    // A line that states a value, its words around it or not (review of 2026-11-13).
    "The area is $A = 24$ cm²",
    "**The area is $A = 24$ cm²**",
    "Die Fläche ist $A = 24$ cm²",
    "Sum of the angles $= 180°$",
    "The hypotenuse $c = 15\\ \\text{cm}$",
    "Maximum height $h = 20$ m",
    "Roots are $x = 3$ and $x = -2$",
    "The ball lands $x = 12\\,\\mathrm{m}$ from the wall.",
    "The speed of the car is about $4.2$ m/s",
    "$9$ apples and $12$ pears",
    "The solution is $x < 9$",
    "Carbon dioxide",
    "Sodium chloride",
    "New York",
    "Not possible",
  ])("reads %s as a value", (line) => {
    expect(isAnswerValue(line)).toBe(true);
  });
});
