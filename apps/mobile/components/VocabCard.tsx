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
  const gloss = card.simpleGloss?.trim();
  const example = card.exampleSentence?.trim();
  const exampleParts = example ? highlightLemmaParts(example, word) : [];

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
          <Icon name="volume-medium-outline" size={22} color={theme.primary} />
        </Pressable>
        {pos ? (
          <View style={s.posChip}>
            <Text style={s.posText}>{pos}</Text>
          </View>
        ) : null}
      </View>
      {gloss ? (
        <View style={s.glossWell}>
          <Text style={s.glossText}>{gloss}</Text>
        </View>
      ) : null}
      <View style={s.section}>
        <Text style={s.sectionLabel}>{t("lesson.meaning")}</Text>
        <Text style={s.definition}>{card.definition}</Text>
      </View>
      {gloss && gloss.toLowerCase() !== card.definition.trim().toLowerCase() ? (
        <View style={s.simpleWell}>
          <Text style={s.simpleText}>
            {t("lesson.in_simple_words", { gloss })}
          </Text>
        </View>
      ) : null}
      {example ? (
        <View style={s.section}>
          <Text style={s.sectionLabel}>{t("lesson.example")}</Text>
          <Text style={s.example}>
            {exampleParts.map((part, index) => (
              <Text key={`${index}-${part.text}`} style={part.match ? s.lemma : undefined}>
                {part.text}
              </Text>
            ))}
          </Text>
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
      paddingVertical: Space.lg,
    },
    word: {
      ...Type.display,
      fontSize: 34,
      lineHeight: 40,
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
      backgroundColor: t.successLight,
    },
    posChip: {
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xxs,
      borderRadius: Radius.full,
      backgroundColor: t.successLight,
    },
    posText: {
      ...Type.caption,
      color: t.success,
      textTransform: "lowercase",
    },
    glossWell: {
      backgroundColor: t.successLight,
      borderRadius: Radius.lg,
      paddingVertical: Space.xl,
      paddingHorizontal: Space.lg,
      alignItems: "center",
      minHeight: 88,
      justifyContent: "center",
    },
    glossText: {
      ...Type.body,
      color: t.success,
      textAlign: "center",
    },
    section: {
      gap: Space.xs,
    },
    sectionLabel: {
      ...Type.label,
      color: t.success,
    },
    definition: {
      ...Type.body,
      color: t.text,
    },
    simpleWell: {
      backgroundColor: t.surfaceAlt,
      borderRadius: Radius.md,
      paddingVertical: Space.sm,
      paddingHorizontal: Space.md,
    },
    simpleText: {
      ...Type.secondary,
      color: t.text,
    },
    example: {
      ...Type.body,
      color: t.text,
    },
    lemma: {
      fontWeight: "700",
      color: t.success,
    },
  });
}
