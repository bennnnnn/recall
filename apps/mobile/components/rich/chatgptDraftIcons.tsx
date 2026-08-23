import Svg, { Path } from "react-native-svg";

/** Official-style Gmail “M” — ChatGPT’s email-card action, not a generic envelope. */
export function GmailMark({ size = 18 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <Path fill="#4285F4" d="M1.5 6.75v10.5A2.25 2.25 0 0 0 3.75 19.5H6v-9.15L12 14.4l6-4.05V19.5h2.25a2.25 2.25 0 0 0 2.25-2.25V6.75L12 13.2 1.5 6.75Z" />
      <Path fill="#EA4335" d="M1.5 6.75 12 13.2 6 9.35V4.5H3.75A2.25 2.25 0 0 0 1.5 6.75Z" />
      <Path fill="#34A853" d="M22.5 6.75A2.25 2.25 0 0 0 20.25 4.5H18v4.85l4.5 2.4V6.75Z" />
      <Path fill="#FBBC04" d="M6 4.5h12v4.85L12 13.2 6 9.35V4.5Z" />
    </Svg>
  );
}
