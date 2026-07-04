import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";
import type { ParsedVocabCard } from "@/lib/parseVocabCard";
import { cleanQuizWord } from "@/lib/parseVocabQuiz";
import { partOfSpeechLabel } from "@/lib/languageLevels";
import { speakWord } from "@/lib/pronunciation";

type Props = {
  card: ParsedVocabCard;
  language?: string;
};

export function VocabCard({ card, language = "en" }: Props) {
  const theme = useTheme();
  const s = makeStyles(theme);
  const { t } = useTranslation();
  const word = cleanQuizWord(card.word);

  const handleSpeak = () => {
    void speakWord(word, { language: language === "en" ? "en-US" : language });
  };

  return (
    <View style={s.card} accessibilityRole="summary">
      <View style={s.header}>
        <Text style={s.word}>{word}</Text>
        {card.partOfSpeech ? (
          <Text style={s.pos}>{partOfSpeechLabel(card.partOfSpeech)}</Text>
        ) : null}
        <Pressable
          onPress={handleSpeak}
          style={s.speakBtn}
          accessibilityRole="button"
          accessibilityLabel={t("quiz.pronunciation_unavailable_title")}
        >
          <Ionicons name="volume-medium-outline" size={20} color={theme.primary} />
        </Pressable>
      </View>
      <Text style={s.definition}>{card.definition}</Text>
      {card.exampleSentence ? (
        <Text style={s.example}>{card.exampleSentence}</Text>
      ) : null}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    card: {
      marginTop: 10,
      padding: 14,
      borderRadius: 14,
      backgroundColor: t.surfaceAlt,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      gap: 8,
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      flexWrap: "wrap",
    },
    word: {
      fontSize: 20,
      fontWeight: "700",
      color: t.text,
    },
    pos: {
      fontSize: 13,
      color: t.textSecondary,
      textTransform: "capitalize",
    },
    speakBtn: {
      marginLeft: "auto",
      padding: 4,
    },
    definition: {
      fontSize: 16,
      lineHeight: 22,
      color: t.text,
    },
    example: {
      fontSize: 15,
      lineHeight: 21,
      color: t.textSecondary,
      fontStyle: "italic",
    },
  });
}
