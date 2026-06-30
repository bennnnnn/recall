import { MathText } from "@/components/rich/MathText";

type Props = {
  latex: string;
  textColor?: string;
};

/** Inline native Text math — no WebView. */
export function MathRenderer({ latex, textColor }: Props) {
  return <MathText latex={latex} textColor={textColor} />;
}
