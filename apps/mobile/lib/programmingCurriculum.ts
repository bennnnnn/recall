/** Mirrors backend PROGRAMMING_CURRICULUM — language-agnostic chapters + sub-topics. */
export const PROGRAMMING_CURRICULUM = [
  {
    chapter: "Getting started",
    topics: [
      "What programming is and what code does",
      "How programs run on your computer",
      "Writing and running your first program",
    ],
  },
  {
    chapter: "Variables",
    topics: [
      "What a variable is",
      "What variables are used for",
      "How to create a variable and assign a value",
      "Reading and changing a variable's value",
      "Naming rules (valid names, case sensitivity)",
      "Choosing clear, meaningful names",
    ],
  },
  {
    chapter: "Data types",
    topics: [
      "Strings — storing text",
      "Numbers — integers and decimals",
      "Booleans — true and false",
      "Checking what type a value is",
    ],
  },
  {
    chapter: "Output and comments",
    topics: [
      "Printing output to the screen",
      "Printing variable values",
      "Writing single-line comments",
      "When comments help and when they don't",
    ],
  },
  {
    chapter: "Operators and math",
    topics: [
      "Arithmetic: add, subtract, multiply, divide",
      "Comparison operators (==, !=, <, >)",
      "Combining conditions with and / or / not",
      "Order of operations in expressions",
    ],
  },
  {
    chapter: "Making decisions",
    topics: [
      "if statements — run code when a condition is true",
      "else and else-if branches",
      "Nested conditions",
      "Common decision patterns in real code",
    ],
  },
  {
    chapter: "Loops",
    topics: [
      "for loops — repeat for each item or a set count",
      "while loops — repeat while a condition is true",
      "When to use for vs while",
      "Avoiding infinite loops",
    ],
  },
  {
    chapter: "Functions",
    topics: [
      "What a function is and why we use them",
      "Defining a function",
      "Parameters — passing values in",
      "Return values — sending a result back",
      "Calling functions you've written",
    ],
  },
  {
    chapter: "Lists and collections",
    topics: [
      "What a list is and when to use one",
      "Creating a list and accessing items by index",
      "Adding and removing list items",
      "Looping over every item in a list",
    ],
  },
  {
    chapter: "Errors and debugging",
    topics: [
      "Syntax errors vs runtime errors",
      "Reading an error message and finding the line",
      "Common beginner mistakes (quotes, spelling, indentation)",
      "Using print to trace what your code is doing",
      "Fixing bugs one step at a time",
    ],
  },
] as const;

export const PROGRAMMING_CHAPTERS = PROGRAMMING_CURRICULUM.map((entry) => entry.chapter);

export function firstProgrammingChapter(): string {
  return PROGRAMMING_CHAPTERS[0];
}

export function programmingChapterIndex(title: string): number {
  const idx = (PROGRAMMING_CHAPTERS as readonly string[]).indexOf(title);
  return idx >= 0 ? idx + 1 : 0;
}
