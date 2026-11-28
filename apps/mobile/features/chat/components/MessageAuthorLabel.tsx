/**
 * Who wrote a message, for a screen reader only: "You said" or "Recall said" before the
 * bubble. A bubble's side and colour told it, which a screen reader never says. The bubble
 * itself stays open (its photo, file and links are reachable one by one), so the name is
 * its own element: one pixel at the bubble's top-left, which both readers reach first.
 */
import { StyleSheet, Text } from "react-native";
import { useTranslation } from "react-i18next";

export function MessageAuthorLabel({ role }: { role: "user" | "assistant" }) {
  const { t } = useTranslation();
  return (
    <Text style={styles.label} testID="message-author" importantForAccessibility="yes">
      {t(role === "user" ? "chat.author_you" : "chat.author_recall")}
    </Text>
  );
}

const styles = StyleSheet.create({
  // Seen by neither eye nor layout; heard first. Opacity 0 would hide it from VoiceOver.
  label: {
    position: "absolute",
    top: 0,
    left: 0,
    width: 1,
    height: 1,
    overflow: "hidden",
    color: "transparent",
  },
});
