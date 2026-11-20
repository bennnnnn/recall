/**
 * What code outside React is handed to translate with: `t` from `useTranslation()`, or a
 * plain function in a test. Two signatures rather than one with an optional `options`,
 * because i18next 27's `TFunction` takes options only through its own overloads, and a
 * function type whose second parameter is optional no longer accepts it.
 */
export type Translate = {
  (key: string): string;
  (key: string, options: Record<string, unknown>): string;
};
