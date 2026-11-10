import { createContext, type ReactNode, useContext } from "react";

const ColumnInset = createContext(0);

/**
 * Draws its children `inset` points in from the reply's left edge: a worked solution's
 * lines start at `WORK_INDENT`. A formula there has that much less room before it reaches
 * the right edge, so it scrolls when it is wider than what is left; judged against the whole
 * column, a line of working 30 points too wide was cut off at the edge ("∫cos((").
 */
export function MathColumn({ inset, children }: { inset: number; children: ReactNode }) {
  const outer = useContext(ColumnInset);
  return <ColumnInset.Provider value={outer + inset}>{children}</ColumnInset.Provider>;
}

/** How far in from the reply's left edge the formula is drawn. */
export function useMathColumnInset(): number {
  return useContext(ColumnInset);
}
