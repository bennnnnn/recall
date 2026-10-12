import { splitWorkoutNote, workoutHeading } from "@/lib/markdown/workoutSection";

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

describe("workoutHeading", () => {
  it.each([
    ["Given", "Given"],
    ["Steps:", "Steps"],
    ["Substitution", "Substitution"],
    ["Diagram", null],
    ["1. Subtract 3", null],
  ])("%s", (text, expected) => {
    expect(workoutHeading(text)).toBe(expected);
  });
});
