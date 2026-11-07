import { createContext, type ReactNode, useContext } from "react";

const InsideAccessibleElement = createContext(false);

/**
 * Wraps what an accessible parent (a quiz option, an answer card, a grouped
 * paragraph) draws: the parent is the screen-reader element and its label
 * already reads the text, maths in words.
 *
 * Nothing inside may be `accessible` too. iOS hides it anyway, but Android's
 * TalkBack gives each focusable child its own stop and leaves it out of the
 * parent's description: a quiz option with maths was read as a wordless
 * "radio button", then the formula as a separate dead stop.
 */
export function AccessibleElementChildren({ children }: { children: ReactNode }) {
  return (
    <InsideAccessibleElement.Provider value>{children}</InsideAccessibleElement.Provider>
  );
}

/** True under an accessible parent: draw without an accessibility element of your own. */
export function useInsideAccessibleElement(): boolean {
  return useContext(InsideAccessibleElement);
}
