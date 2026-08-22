import { Pressable, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/components/Icon";
import { useTranslation } from "react-i18next";

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
      <View style={s.header}>
        <Text style={s.word}>{word}</Text>
        <Pressable
          onPress={handleSpeak}
          style={s.speakBtn}
          accessibilityRole="button"
          accessibilityLabel={t("quiz.pronunciation_unavailable_title")}
        >
          <Icon name="volume-medium-outline" size={20} color={theme.primary} />
        </Pressable>
      </View>
      <View style={s.section}>
        <Text style={s.label}>{t("lesson.definition_label")}</Text>
        <Text style={s.definition}>{card.definition}</Text>
      </View>
      {card.exampleSentence ? (
        <View style={s.section}>
          <Text style={s.label}>{t("lesson.example_label")}</Text>
          <Text style={s.example}>{card.exampleSentence}</Text>
        </View>
      ) : null}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    card: {
      marginTop: Space.sm,
      backgroundColor: t.bg,
      gap: Space.lg,
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      flexWrap: "wrap",
    },
    word: {
      fontSize: 26,
      fontWeight: "700",
      color: t.text,
    },
    speakBtn: {
      marginLeft: "auto",
      padding: 4,
    },
    section: {
      gap: Space.xs,
    },
    label: {
      ...Type.caption,
      fontWeight: "600",
      color: t.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.5,
    },
    definition: {
      ...Type.body,
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
