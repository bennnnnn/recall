import { Pressable, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/components/Icon";
import { useTranslation } from "react-i18next";

import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import type { ParsedVocabCard } from "@/lib/parseVocabCard";
import { cleanQuizWord } from "@/lib/parseVocabQuiz";
import { speakWord } from "@/lib/pronunciation";
import { useAuthToken } from "@/contexts/AuthContext";

type Props = {
  card: ParsedVocabCard;
  language?: string;
};

export function VocabCard({ card, language = "en" }: Props) {
  const theme = useTheme();
  const s = makeStyles(theme);
  const { t } = useTranslation();
  const token = useAuthToken();
  const word = cleanQuizWord(card.word);

  const handleSpeak = () => {
    void speakWord(word, {
      language: language === "en" ? "en-US" : language,
      token,
    });
  };

  return (
    <View style={s.card} accessibilityRole="summary">
      <View style={s.wordRow}>
        <Text style={s.word}>{word}</Text>
        <Pressable
          onPress={handleSpeak}
          style={s.speakBtn}
          accessibilityRole="button"
          accessibilityLabel={t("quiz.pronunciation_unavailable_title")}
        >
          <Icon name="volume-medium-outline" size={24} color={theme.primary} />
        </Pressable>
      </View>
      <View style={s.details}>
        <Text style={s.definition}>{card.definition}</Text>
        {card.exampleSentence ? (
          <Text style={s.example}>{card.exampleSentence}</Text>
        ) : null}
      </View>
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    card: {
      alignSelf: "stretch",
      alignItems: "center",
      gap: Space.md,
      paddingVertical: Space.xl,
      paddingHorizontal: Space.lg,
      backgroundColor: t.surfaceAlt,
      borderRadius: Radius.xl,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
    },
    wordRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: Space.sm,
    },
    word: {
      fontSize: 30,
      fontWeight: "700",
      color: t.text,
      textAlign: "center",
    },
    speakBtn: {
      padding: Space.xxs,
    },
    details: {
      alignItems: "center",
      gap: Space.sm,
      maxWidth: 320,
    },
    definition: {
      ...Type.body,
      color: t.textSecondary,
      textAlign: "center",
    },
    example: {
      fontSize: 15,
      lineHeight: 21,
      color: t.textTertiary,
      fontStyle: "italic",
      textAlign: "center",
    },
  });
}
