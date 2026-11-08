/**
 * "By continuing, you agree to the Terms and Privacy Policy", with the two names as links
 * in the sentence. It is one translated string whose links are marked `<terms>…</terms>`
 * and `<privacy>…</privacy>`, so each language keeps its own word order; the pieces wrap
 * as one centred line, and each link is a 44pt target. The sign-in tap below it also
 * records the account's AI-data consent (`features/auth/api.ts`).
 */
import {
  Pressable,
  type StyleProp,
  StyleSheet,
  Text,
  type TextStyle,
  View,
} from "react-native";
import { useTranslation } from "react-i18next";

import { getLegalPrivacyUrl, getLegalTermsUrl } from "@/lib/legalUrls";
import { openAllowedUrl } from "@/lib/linkSchemePolicy";
import { Space } from "@/lib/space";

type Props = { style: StyleProp<TextStyle>; linkStyle: StyleProp<TextStyle> };

const MARKED = /<(terms|privacy)>(.*?)<\/\1>/g;
/** A 12pt line is about 17pt tall: this makes each link a 45pt target. */
const LINK_SLOP = { top: 14, bottom: 14, left: Space.xxs, right: Space.xxs };

type Piece = { text: string; link?: "terms" | "privacy" };

/** The sentence cut at its links: plain runs and the two marked names, in order, each
 * without its edge spaces; ``spaced`` says whether the sentence has a word gap before it,
 * so "Policy." and Turkish "Koşullar'ı" stay glued to their link. */
export function agreePieces(sentence: string): (Piece & { spaced: boolean })[] {
  const raw: Piece[] = [];
  let at = 0;
  for (const match of sentence.matchAll(MARKED)) {
    const index = match.index ?? 0;
    if (index > at) raw.push({ text: sentence.slice(at, index) });
    raw.push({ text: match[2], link: match[1] as Piece["link"] });
    at = index + match[0].length;
  }
  if (at < sentence.length) raw.push({ text: sentence.slice(at) });
  const pieces: (Piece & { spaced: boolean })[] = [];
  let gap = false;
  for (const piece of raw) {
    const text = piece.text.trim();
    gap = gap || /^\s/.test(piece.text);
    if (text) {
      pieces.push({ ...piece, text, spaced: pieces.length > 0 && gap });
      gap = /\s$/.test(piece.text);
    }
  }
  return pieces;
}

export function AgreeLine({ style, linkStyle }: Props) {
  const { t } = useTranslation();
  return (
    <View style={s.row}>
      {agreePieces(t("login.agree_line")).map((piece, index) =>
        piece.link ? (
          <Pressable
            key={piece.link}
            style={piece.spaced && s.gap}
            onPress={() =>
              void openAllowedUrl(
                piece.link === "terms"
                  ? getLegalTermsUrl()
                  : getLegalPrivacyUrl(),
              )
            }
            accessibilityRole="link"
            accessibilityLabel={t(
              piece.link === "terms" ? "login.terms" : "login.privacy",
            )}
            hitSlop={LINK_SLOP}
          >
            <Text style={[style, linkStyle]}>{piece.text}</Text>
          </Pressable>
        ) : (
          <Text key={`text-${index}`} style={[style, piece.spaced && s.gap]}>
            {piece.text}
          </Text>
        ),
      )}
    </View>
  );
}

const s = StyleSheet.create({
  row: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    paddingHorizontal: Space.xs,
  },
  // One word space between pieces, the same width before and after each link.
  gap: { marginLeft: Space.xxs },
});
