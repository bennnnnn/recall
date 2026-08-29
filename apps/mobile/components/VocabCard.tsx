import { Pressable, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/components/Icon";
import { useTranslation } from "react-i18next";

import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { cleanQuizWord } from "@/lib/parseVocabQuiz";
import { speakWord } from "@/lib/pronunciation";
import { useAuthToken } from "@/contexts/AuthContext";
import {
  exampleSentences,
  highlightLemmaParts,
  type LessonVocabCard,
} from "@/lib/projects/chapterLesson";

type Props = {
  card: LessonVocabCard;
  language?: string;
};

export function VocabCard({ card, language = "en" }: Props) {
  const theme = useTheme();
  const s = makeStyles(theme);
  const { t } = useTranslation();
  const token = useAuthToken();
  const word = cleanQuizWord(card.word);
  const ipa = card.ipa?.trim();
  const pos = card.partOfSpeech?.trim();
  const examples = exampleSentences(card.exampleSentence);

  const handleSpeak = () => {
    void speakWord(word, {
      language: language === "en" ? "en-US" : language,
      token,
    });
  };

  return (
    <View style={s.card} accessibilityRole="summary">
      <Text style={s.word}>{word}</Text>
      <View style={s.metaRow}>
        {ipa ? <Text style={s.ipa}>/{ipa}/</Text> : null}
        <Pressable
          onPress={handleSpeak}
          style={s.speakBtn}
          accessibilityRole="button"
          accessibilityLabel={t("lesson.speak")}
        >
          <Icon name="volume-medium-outline" size={20} color={theme.primary} />
        </Pressable>
        {pos ? (
          <View style={s.posChip}>
            <Text style={s.posText}>{pos}</Text>
          </View>
        ) : null}
      </View>
      <Text style={s.definition}>{card.definition}</Text>
      {examples.length > 0 ? (
        <View style={s.examples}>
          {examples.map((sentence) => (
            <Text key={sentence} style={s.example}>
              {highlightLemmaParts(sentence, word).map((part, index) => (
                <Text key={`${index}-${part.text}`} style={part.match ? s.lemma : undefined}>
                  {part.text}
                </Text>
              ))}
            </Text>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    card: {
      alignSelf: "stretch",
      gap: Space.md,
      paddingVertical: Space.sm,
    },
    word: {
      ...Type.display,
      fontSize: 32,
      lineHeight: 38,
      color: t.text,
    },
    metaRow: {
      flexDirection: "row",
      alignItems: "center",
      flexWrap: "wrap",
      gap: Space.sm,
    },
    ipa: {
      ...Type.secondary,
      color: t.textSecondary,
    },
    speakBtn: {
      width: 36,
      height: 36,
      borderRadius: 18,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: t.primaryLight,
    },
    posChip: {
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xxs,
      borderRadius: Radius.full,
      backgroundColor: t.surfaceAlt,
    },
    posText: {
      ...Type.caption,
      color: t.textSecondary,
      textTransform: "lowercase",
    },
    definition: {
      ...Type.body,
      fontSize: 17,
      lineHeight: 26,
      color: t.text,
    },
    examples: {
      gap: Space.sm,
      paddingTop: Space.xs,
    },
    example: {
      ...Type.body,
      color: t.textSecondary,
    },
    lemma: {
      fontWeight: "700",
      color: t.text,
    },
  });
}
