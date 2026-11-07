/**
 * The answer line at the top of a worked reply, and the two scopes it needs: the chat's
 * scroller (`ScrollToViewProvider`, which the chat screen gives its message list) and the
 * reply's first answer card (`AnswerAnchorScope`, which every ```answer card registers
 * with). Outside a chat, or in a reply with no card on screen, the line is not drawn.
 */
import {
  createContext,
  Fragment,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Pressable, StyleSheet, Text, type HostInstance } from "react-native";
import { useTranslation } from "react-i18next";

import { PARAGRAPH_GAP } from "@/components/markdown/markdownContentStyles";
import { MathText } from "@/components/rich/MathText";
import type { AnswerJump } from "@/lib/markdown/answerJump";
import { readableLatexFallback } from "@/lib/math/text";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

/** Scrolls the chat so `target` (a view inside a message) is in view. */
export type ScrollToView = (target: HostInstance) => void;

const ScrollToViewContext = createContext<ScrollToView | null>(null);

export function ScrollToViewProvider({ scrollTo, children }: { scrollTo: ScrollToView; children: ReactNode }) {
  return <ScrollToViewContext.Provider value={scrollTo}>{children}</ScrollToViewContext.Provider>;
}

type AnchorRegistry = {
  /** A card's ref callback: the first card on screen is the one the line leads to. */
  register: (view: HostInstance | null, key: object) => void;
  first: () => HostInstance | null;
  /** Whether a card is on screen, so the line is drawn only with somewhere to go. */
  present: boolean;
};

const AnswerAnchorContext = createContext<AnchorRegistry | null>(null);

/** One reply's answer cards, in the order they mounted (the reply's reading order). */
export function AnswerAnchorScope({ children }: { children: ReactNode }) {
  const cards = useRef<{ key: object; view: HostInstance }[]>([]);
  const [present, setPresent] = useState(false);
  const register = useCallback((view: HostInstance | null, key: object) => {
    const rest = cards.current.filter((card) => card.key !== key);
    cards.current = view ? [...rest, { key, view }] : rest;
    setPresent(cards.current.length > 0);
  }, []);
  const registry = useMemo<AnchorRegistry>(
    () => ({ register, first: () => cards.current[0]?.view ?? null, present }),
    [register, present],
  );
  return <AnswerAnchorContext.Provider value={registry}>{children}</AnswerAnchorContext.Provider>;
}

/** The ref an answer card puts on its frame, so the reply's answer line can lead to it. */
export function useAnswerAnchorRef(): ((view: HostInstance | null) => void) | undefined {
  // `register` alone, never the registry: its `present` changing must not hand the card a new ref.
  const register = useContext(AnswerAnchorContext)?.register;
  const key = useRef({}).current;
  return useMemo(
    () => (register ? (view: HostInstance | null) => register(view, key) : undefined),
    [register, key],
  );
}

/** Units, spacing and plain operators: what a value can hold and still be set as words. */
const FLAT_LATEX = /\\(?:text|mathrm)\{[^{}]*\}|\\[,;:! ]|\\(?:times|cdot|approx|pm|degree)\b/g;

/**
 * A value with no structure ("x = 4", "50\ \mathrm{m}") as words, so the line is bold as
 * a model's "**x = 3**" is; null for a fraction, power or root, which stays typeset.
 */
function flatValue(latex: string): string | null {
  if (/[\\^_{}]/.test(latex.replace(FLAT_LATEX, ""))) return null;
  return readableLatexFallback(latex).replace(/\s+/g, " ").trim();
}

function spoken(jump: AnswerJump): string {
  return jump.values
    .map((value) => (value.notation === "chemistry" ? value.text : readableLatexFallback(value.text)))
    .join(", ");
}

/**
 * "11.5 m · 3.06 s": the values of a reply's cards as its first line, in bold reply ink as
 * a model opens with its answer, typeset as the cards set them. A tap scrolls to the first
 * card, where the check is. No label and no chevron: the answer is a line of the reply, not
 * a control beside it (November 2026).
 */
export function AnswerLead({ jump }: { jump: AnswerJump }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const scrollTo = useContext(ScrollToViewContext);
  const anchors = useContext(AnswerAnchorContext);
  if (!scrollTo || !anchors?.present) return null;
  const ink = { color: theme.text };
  return (
    <Pressable
      testID="answer-jump"
      accessibilityRole="button"
      accessibilityLabel={t("rich.answer_a11y", { text: spoken(jump) })}
      accessibilityHint={t("rich.answer_jump_hint")}
      onPress={() => {
        const card = anchors.first();
        if (card) scrollTo(card);
      }}
      style={styles.lead}
    >
      {jump.values.map((value, i) => (
        <Fragment key={i}>
          {i > 0 ? <Text style={[styles.value, ink]}>·</Text> : null}
          {value.notation === "chemistry" || flatValue(value.text) != null ? (
            <Text style={[styles.value, ink]}>
              {value.notation === "chemistry" ? value.text : flatValue(value.text)}
            </Text>
          ) : (
            <MathText latex={value.text} textColor={theme.text} fontSize={Type.reading.fontSize} />
          )}
        </Fragment>
      ))}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  lead: {
    alignSelf: "flex-start",
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    gap: Space.xs,
    marginBottom: PARAGRAPH_GAP,
  },
  value: { ...Type.reading, ...Weight.bold },
});
