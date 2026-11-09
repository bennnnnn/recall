import { StyleSheet, Text, type StyleProp, type TextStyle } from "react-native";

import { Weight } from "@/lib/type";

/**
 * A no-break space, so the pill's edge never wraps away from the code. It is
 * set in the UI face (0.2em) because SpaceMono's is a full 0.6em cell.
 */
const PAD = " ";

/**
 * Code up to this long keeps together: its spaces do not break, so "+ 1" and
 * "range(1, 6)" never split over two lines. About half a line of 14pt code; a longer
 * span may wrap at its spaces, or it would run past the edge of the reply.
 */
const UNBROKEN_CODE = 24;

/** `code` with no-break spaces when it is short enough to stay on one line. */
function unbrokenCode(code: string): string {
  return code.length <= UNBROKEN_CODE ? code.replace(/ /g, "\u00A0") : code;
}

/**
 * Inline code drawn as a pill: `style` gives the face and tint (see
 * `inlineCodeTextStyle`). Inside a sentence this is a nested Text, which
 * takes no padding or corner radius on iOS or Android, so the tint is the
 * span's background and a thin no-break space pads each end. Where the code
 * stands alone in a row (a callout's wrapped words, a run beside a stacked
 * fraction) the same style also rounds the corners.
 */
export function InlineCode({
  children,
  style,
}: {
  children: string;
  style?: StyleProp<TextStyle>;
}) {
  return (
    <Text style={style} selectable>
      <Text style={styles.pad}>{PAD}</Text>
      {unbrokenCode(children)}
      <Text style={styles.pad}>{PAD}</Text>
    </Text>
  );
}

const styles = StyleSheet.create({
  // About 4pt at the 14pt code size: the space's 0.2em plus this tracking.
  pad: { ...Weight.regular, letterSpacing: 1.2 },
});
