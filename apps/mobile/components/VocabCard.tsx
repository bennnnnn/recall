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
  textScale?: number;
  onSpeak?: () => void;
};

const SPEAK = 52;
const COMPACT_WORD = 18;

export function VocabCard({ card, language = "en", textScale = 1, onSpeak }: Props) {
  const theme = useTheme();
  const s = makeStyles(theme, textScale);
  const { t } = useTranslation();
  const token = useAuthToken();
  const word = cleanQuizWord(card.word);
  const ipa = card.ipa?.trim();
  const meaning = cardMeaning(card);
  const examples = card.examples?.length ? card.examples : exampleSentences(card.exampleSentence);
  const compactWord = word.length > COMPACT_WORD;

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
      <View style={s.entry}>
        <View style={s.hero}>
          <Pressable onPress={handleSpeak} style={s.heroText} accessible={false}>
            <Text style={[s.word, compactWord && s.wordCompact]} accessibilityRole="header">
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
      </View>

      {examples.length > 0 ? (
        <View style={s.examples}>
          {examples.map((sentence) => (
            <View key={sentence} style={s.quote}>
              <Text style={s.example}>
                {highlightLemmaParts(sentence, word).map((part, index) =>
                  part.match ? (
                    <Text key={`${index}-m`} style={s.lemma}>
                      {part.text}
                    </Text>
                  ) : (
                    <Text key={`${index}-r`}>{part.text}</Text>
                  ),
                )}
              </Text>
            </View>
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

function makeStyles(t: Theme, scale: number) {
  const n = (size: number) => Math.round(size * scale);
  return StyleSheet.create({
    root: {
      alignSelf: "stretch",
      gap: Space.lg,
    },
    entry: {
      gap: Space.md,
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
      fontSize: n(30),
      lineHeight: n(36),
      fontWeight: "800",
      color: t.text,
    },
    wordCompact: {
      fontSize: n(26),
      lineHeight: n(32),
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
      fontSize: n(17),
      color: t.textSecondary,
    },
    meaning: {
      fontSize: n(20),
      lineHeight: n(28),
      color: t.text,
    },
    examples: {
      gap: Space.sm,
    },
    quote: {
      paddingVertical: Space.md,
      paddingHorizontal: Space.md,
      borderRadius: Radius.lg,
      backgroundColor: t.bg,
      borderWidth: 1,
      borderColor: t.border,
    },
    example: {
      fontSize: n(18),
      lineHeight: n(26),
      color: t.textSecondary,
    },
    lemma: {
      fontWeight: "700",
      color: t.text,
    },
  });
}
