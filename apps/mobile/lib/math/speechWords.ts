/**
 * The words a formula is spoken with (`spokenFormula`), in the app's language: a screen
 * reader's label and read-aloud said "x squared" and "the square root of" in English
 * whatever the language. Each is a key under `math_speech.` in every locale; a phrase
 * whose word order differs by language is a template, its blanks in single braces
 * (`{x}`, `{num}`, `{den}`, `{n}`), which i18next leaves alone.
 *
 * lib/i18n sets the words whenever the language changes (`setMathSpeechWords`), so this
 * module stays free of i18next and a test that never loads it hears English.
 */
import { useSyncExternalStore } from "react";

import type { Translate } from "@/lib/i18n/translate";
import { createValueStore } from "@/lib/listenerSet";
import type { MathAccentKind } from "@/lib/math/textTypes";

const WORD_KEYS = [
  "plus_minus",
  "times",
  "dot",
  "over",
  "all_over",
  "quantity",
  "subscript",
  "squared",
  "cubed",
  "power",
  "degrees",
  "mixed",
  "sqrt",
  "cbrt",
  "root",
  "accent_bar",
  "accent_underline",
  "accent_hat",
  "accent_tilde",
  "accent_vector",
  "accent_dot",
  "accent_ddot",
] as const;

export type MathSpeechWord = (typeof WORD_KEYS)[number];

export type MathSpeechWords = {
  words: Record<MathSpeechWord, string>;
  /** English says a mixed number's fraction in ordinals ("2 and 1 half"). */
  ordinals: boolean;
};

/** lib/i18n/en.json's `math_speech.*`, before any language is set (a test, a pure caller). */
export const ENGLISH_MATH_SPEECH: MathSpeechWords = {
  ordinals: true,
  words: {
    plus_minus: "plus or minus",
    times: "times",
    dot: "dot",
    over: "{num} over {den}",
    all_over: "{num}, all over {den}",
    quantity: "the quantity {x}",
    subscript: "subscript {x}",
    squared: "squared",
    cubed: "cubed",
    power: "to the power of {x}",
    degrees: "degrees",
    mixed: "and {num} over {den}",
    sqrt: "the square root of {x}",
    cbrt: "the cube root of {x}",
    root: "the {n} root of {x}",
    accent_bar: "{x} bar",
    accent_underline: "{x} underlined",
    accent_hat: "{x} hat",
    accent_tilde: "{x} tilde",
    accent_vector: "{x} vector",
    accent_dot: "{x} dot",
    accent_ddot: "{x} double dot",
  },
};

export const ACCENT_WORD: Record<MathAccentKind, MathSpeechWord> = {
  overline: "accent_bar",
  underline: "accent_underline",
  hat: "accent_hat",
  tilde: "accent_tilde",
  vec: "accent_vector",
  vecLeft: "accent_vector",
  bar: "accent_bar",
  dot: "accent_dot",
  ddot: "accent_ddot",
};

const current = createValueStore<MathSpeechWords>(ENGLISH_MATH_SPEECH);

export function mathSpeechWords(): MathSpeechWords {
  return current.get();
}

export function setMathSpeechWords(words: MathSpeechWords): void {
  current.set(words);
}

/** The words formulas are spoken with: a label drawn with them reads again when they change. */
export function useMathSpeechWords(): MathSpeechWords {
  return useSyncExternalStore(current.subscribe, current.get, current.get);
}

/** The words of `language`, read through its `t`. */
export function readMathSpeechWords(t: Translate, language: string): MathSpeechWords {
  if (language === "en") return ENGLISH_MATH_SPEECH;
  const words = {} as Record<MathSpeechWord, string>;
  for (const key of WORD_KEYS) words[key] = t(`math_speech.${key}`);
  return { words, ordinals: false };
}

/** A template with its blanks filled: `fillWord("{num} over {den}", { num: "1", den: "2" })`. */
export function fillWord(template: string, values: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (blank, name: string) => values[name] ?? blank);
}
