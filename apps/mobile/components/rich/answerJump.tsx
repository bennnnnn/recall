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
import { StyleSheet, Text, type HostInstance } from "react-native";
import { useTranslation } from "react-i18next";

import { MathText } from "@/components/rich/MathText";
import type { AnswerJump } from "@/lib/markdown/answerJump";
import { readableLatexFallback } from "@/lib/math/text";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Chip } from "@/ui/controls/Chip";
import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";

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
  const registry = useContext(AnswerAnchorContext);
  const key = useRef({}).current;
  return useMemo(
    () => (registry ? (view: HostInstance | null) => registry.register(view, key) : undefined),
    // `register` is stable; `present` changing must not hand the card a new ref.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [registry?.register, key],
  );
}

function spoken(jump: AnswerJump): string {
  return jump.values
    .map((value) => (value.notation === "chemistry" ? value.text : readableLatexFallback(value.text)))
    .join(", ");
}

/**
 * "Answer 11.5 m · 3.06 s ⌄": the values of a reply's cards, typeset as the cards set
 * them, in a chip that scrolls to the first card. A value too long for one line is left
 * out and the chip only names the answer.
 */
export function AnswerJumpChip({ jump }: { jump: AnswerJump }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const scrollTo = useContext(ScrollToViewContext);
  const anchors = useContext(AnswerAnchorContext);
  if (!scrollTo || !anchors?.present) return null;
  const label = t("rich.answer_label");
  const text = spoken(jump);
  const ink = { color: theme.text };
  return (
    <Chip
      label={label}
      testID="answer-jump"
      accessibilityLabel={text ? t("rich.answer_a11y", { text }) : label}
      accessibilityHint={t("rich.answer_jump_hint")}
      onPress={() => {
        const card = anchors.first();
        if (card) scrollTo(card);
      }}
      style={styles.chip}
    >
      <Text style={[styles.label, { color: theme.textSecondary }]}>{label}</Text>
      {jump.values.map((value, i) => (
        <Fragment key={i}>
          {i > 0 ? <Text style={[styles.value, ink]}>·</Text> : null}
          {value.notation === "chemistry" ? (
            <Text style={[styles.value, ink]}>{value.text}</Text>
          ) : (
            <MathText latex={value.text} textColor={theme.text} fontSize={Type.secondary.fontSize} />
          )}
        </Fragment>
      ))}
      <Icon name="chevron-down" size={IconSize.xs} color={theme.textSecondary} />
    </Chip>
  );
}

const styles = StyleSheet.create({
  chip: { alignSelf: "flex-start", marginBottom: Space.sm },
  label: { ...Type.secondary, ...Weight.semibold },
  value: { ...Type.secondary },
});
