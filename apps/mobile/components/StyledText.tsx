import { Text, TextProps } from "./Themed";
import { CODE_FONT } from "@/lib/fonts";

export function MonoText(props: TextProps) {
  return <Text {...props} style={[props.style, { fontFamily: CODE_FONT }]} />;
}
