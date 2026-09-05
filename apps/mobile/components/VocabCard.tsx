import { Pressable, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/components/Icon";
import { useTranslation } from "react-i18next";

import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { tap } from "@/lib/haptics";
import { cleanQuizWord } from "@/lib/parseVocabQuiz";
import { speakWord } from "@/lib/pronunciation";
import { useAuthToken } from "@/contexts/AuthContext";
import {
  cardMeaning,
  exampleSentences,
  highlightLemmaParts,
  type LessonVocabCard,
} from "@/lib/projects/chapterLesson";

type Props = {
  card: LessonVocabCard;
  language?: string;
  onSpeak?: () => void;
};

const SPEAK = 52;

export function VocabCard({ card, language = "en", onSpeak }: Props) {
  const theme = useTheme();
  const s = makeStyles(theme);
  const { t } = useTranslation();
  const token = useAuthToken();
  const word = cleanQuizWord(card.word);
  const ipa = card.ipa?.trim();
  const meaning = cardMeaning(card);
  const examples = card.examples?.length ? card.examples : exampleSentences(card.exampleSentence);

  const handleSpeak = () => {
    if (onSpeak) {
      onSpeak();
      return;
    }
    tap();
    void speakWord(word, {
      language: language === "en" ? "en-US" : language,
      token,
      pronunciationUrl: card.pronunciationUrl,
    });
  };

  return (
    <View style={s.root} accessibilityRole="summary">
      <View style={s.hero}>
        <Pressable onPress={handleSpeak} style={s.heroText} accessible={false}>
          <Text style={s.word} accessibilityRole="header">
            {word}
          </Text>
          {ipa ? <Text style={s.ipa}>{formatIpa(ipa)}</Text> : null}
        </Pressable>
        <Pressable
          onPress={handleSpeak}
          style={s.speakBtn}
          accessibilityRole="button"
          accessibilityLabel={t("lesson.speak")}
        >
          <Icon name="volume-medium-outline" size={22} color={theme.onPrimary} />
        </Pressable>
      </View>

      <Text style={s.meaning}>{meaning}</Text>

      {examples.length > 0 ? (
        <View style={s.examples}>
          {examples.map((sentence) => (
            <Text key={sentence} style={s.example}>
              {highlightLemmaParts(sentence, word).map((part, index) =>
                part.match ? (
                  <Text key={`${index}-m`} style={s.lemma}>
                    {part.text}
                  </Text>
                ) : (
                  <Text key={`${index}-r`} style={s.exampleRest}>
                    {part.text}
                  </Text>
                ),
              )}
            </Text>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function formatIpa(ipa: string): string {
  const cleaned = ipa.replaceAll("\u02CC", "").trim();
  return `/${cleaned}/`;
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    root: {
      alignSelf: "stretch",
      gap: Space.lg,
      padding: Space.lg,
      borderRadius: Radius.sheet,
      backgroundColor: t.surface,
    },
    hero: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.md,
    },
    heroText: {
      flex: 1,
      gap: Space.xs,
    },
    word: {
      ...Type.display,
      fontSize: 36,
      lineHeight: 42,
      fontWeight: "800",
      color: t.text,
    },
    speakBtn: {
      width: SPEAK,
      height: SPEAK,
      borderRadius: SPEAK / 2,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: t.primary,
    },
    ipa: {
      ...Type.secondary,
      fontSize: 17,
      color: t.textSecondary,
    },
    meaning: {
      fontSize: 22,
      lineHeight: 32,
      color: t.text,
    },
    examples: {
      gap: Space.xs,
    },
    example: {
      fontSize: 20,
      lineHeight: 30,
      color: t.textSecondary,
    },
    exampleRest: {
      fontStyle: "italic",
    },
    lemma: {
      fontStyle: "normal",
      fontWeight: "700",
      color: t.text,
    },
  });
}
