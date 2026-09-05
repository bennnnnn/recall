import { Pressable, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/components/Icon";
import { useTranslation } from "react-i18next";

import type { IoniconName } from "@/lib/icons";
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

const SPEAK = 56;
const SECTION_GAP = 28;
const AFTER_HERO = 8;

export function VocabCard({ card, language = "en", onSpeak }: Props) {
  const theme = useTheme();
  const s = makeStyles(theme);
  const { t } = useTranslation();
  const token = useAuthToken();
  const word = cleanQuizWord(card.word);
  const ipa = card.ipa?.trim();
  const pos = card.partOfSpeech?.trim();
  const meaning = cardMeaning(card);
  const examples = card.examples?.length ? card.examples : exampleSentences(card.exampleSentence);
  const labels = [
    card.vocabularyKind && card.vocabularyKind !== "word"
      ? t(`lesson.kind.${card.vocabularyKind}`)
      : pos,
    card.verbKind ? t(`lesson.kind.${card.verbKind}`) : null,
    card.nounKind ? t(`lesson.kind.${card.nounKind}`) : null,
  ].filter(Boolean);

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
        <View style={s.wordRow}>
          <Text style={s.word} accessibilityRole="header">
            {word}
          </Text>
          <Pressable
            onPress={handleSpeak}
            style={s.speakBtn}
            accessibilityRole="button"
            accessibilityLabel={t("lesson.speak")}
          >
            <Icon name="volume-medium-outline" size={24} color={theme.primary} />
          </Pressable>
        </View>
        {ipa ? <Text style={s.ipa}>{formatIpa(ipa)}</Text> : null}
        {labels.length ? (
          <View style={s.posChip}>
            <Text style={s.posText}>{labels.join(" · ")}</Text>
          </View>
        ) : null}
      </View>

      <View style={[s.block, s.afterHero]}>
        <Badge icon="book-outline" label={t("lesson.meaning")} theme={theme} />
        <Text style={s.meaning}>{meaning}</Text>
      </View>

      {examples.length > 0 ? (
        <View style={s.block}>
          <Badge icon="pencil-outline" label={t("lesson.example")} theme={theme} />
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

function Badge({ icon, label, theme }: { icon: IoniconName; label: string; theme: Theme }) {
  const s = makeBadge(theme);
  return (
    <View style={s.wrap}>
      <Icon name={icon} size={12} color={theme.primary} />
      <Text style={s.label}>{label}</Text>
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    root: {
      alignSelf: "stretch",
      gap: SECTION_GAP,
    },
    hero: {
      gap: Space.md,
    },
    wordRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: Space.md,
    },
    word: {
      ...Type.display,
      flex: 1,
      fontSize: 38,
      lineHeight: 44,
      fontWeight: "800",
      color: t.text,
    },
    speakBtn: {
      width: SPEAK,
      height: SPEAK,
      borderRadius: SPEAK / 2,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: t.bg,
      borderWidth: 2,
      borderColor: t.primary,
    },
    ipa: {
      ...Type.secondary,
      fontSize: 15,
      color: t.textSecondary,
    },
    posChip: {
      alignSelf: "flex-start",
      paddingHorizontal: 12,
      paddingVertical: 4,
      borderRadius: Radius.full,
      backgroundColor: t.primaryLight,
    },
    posText: {
      fontSize: 13,
      fontWeight: "600",
      color: t.primary,
    },
    block: {
      gap: Space.md,
    },
    afterHero: {
      paddingTop: AFTER_HERO,
    },
    meaning: {
      fontSize: 21,
      lineHeight: 30,
      color: t.text,
    },
    example: {
      fontSize: 18,
      lineHeight: 28,
      color: t.text,
    },
    exampleRest: {
      fontStyle: "italic",
    },
    lemma: {
      fontStyle: "normal",
      fontWeight: "700",
      color: t.success,
    },
  });
}

function makeBadge(t: Theme) {
  return StyleSheet.create({
    wrap: {
      flexDirection: "row",
      alignItems: "center",
      alignSelf: "flex-start",
      gap: 5,
      paddingHorizontal: 10,
      paddingVertical: 5,
      borderRadius: Radius.full,
      backgroundColor: t.primaryLight,
    },
    label: {
      fontSize: 10,
      fontWeight: "700",
      letterSpacing: 0.6,
      textTransform: "uppercase",
      color: t.primary,
    },
  });
}
