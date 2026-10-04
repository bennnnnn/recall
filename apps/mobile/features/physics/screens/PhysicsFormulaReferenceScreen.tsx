import { useMemo, useRef, useState } from "react";
import { FlatList, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { MathText } from "@/components/rich/MathText";
import { StackBackButton } from "@/ui/controls/StackBackButton";
import { SegmentedControl, type Segment } from "@/ui/controls/SegmentedControl";
import { TextField } from "@/ui/controls/TextField";
import { ListRow } from "@/ui/list/ListRow";
import { SelectMenu, type SelectOption } from "@/ui/overlay/SelectMenu";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Type, Weight } from "@/lib/type";
import { useTheme } from "@/lib/theme";

import {
  PHYSICS_CONSTANTS,
  PHYSICS_FORMULA_COUNT,
  PHYSICS_TOPICS,
  physicsConstantEquation,
  searchPhysicsConstants,
  searchPhysicsFormulas,
  type PhysicsConstant,
  type PhysicsEducationLevel,
  type PhysicsFormulaRow,
} from "../model/formulaReference";

type ReferenceTab = "formulas" | "constants";
type LevelFilter = PhysicsEducationLevel | "all";
type TopicFilter = string | "all";

const LEVELS: readonly Segment<LevelFilter>[] = [
  { key: "all", label: "All" },
  { key: "middle_school", label: "Middle" },
  { key: "high_school", label: "High / AP" },
  { key: "undergraduate", label: "Undergrad" },
];

function levelKey(level: PhysicsEducationLevel): string {
  return `physics.reference.${level}`;
}

function FormulaCard({ formula }: { formula: PhysicsFormulaRow }) {
  const theme = useTheme();
  const styles = useMemo(() => makeStyles(theme), [theme]);
  const { t } = useTranslation();
  return (
    <View style={styles.card} testID={`physics-formula-${formula.id}`}>
      <Text style={styles.eyebrow}>{formula.topic}</Text>
      <Text style={styles.cardTitle}>{formula.name}</Text>
      <View style={styles.equation}>
        <MathText latex={formula.equation} textColor={theme.text} fontSize={18} scrollOverflow />
      </View>
      {formula.note ? <Text style={styles.note}>{formula.note}</Text> : null}
      <Text style={styles.level}>{t(levelKey(formula.level))}</Text>
    </View>
  );
}

function ConstantCard({ item }: { item: PhysicsConstant }) {
  const theme = useTheme();
  const styles = useMemo(() => makeStyles(theme), [theme]);
  return (
    <View style={styles.card} testID={`physics-constant-${item.id}`}>
      <Text style={styles.cardTitle}>{item.name}</Text>
      <View style={styles.equation}>
        <MathText
          latex={physicsConstantEquation(item)}
          textColor={theme.text}
          fontSize={18}
          scrollOverflow
        />
      </View>
      <Text style={styles.constantUnit}>{item.unit}</Text>
      {item.note ? <Text style={styles.level}>{item.note}</Text> : null}
    </View>
  );
}

export default function PhysicsFormulaReferenceScreen() {
  const theme = useTheme();
  const styles = useMemo(() => makeStyles(theme), [theme]);
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  const topicAnchor = useRef<View>(null);
  const [tab, setTab] = useState<ReferenceTab>("formulas");
  const [level, setLevel] = useState<LevelFilter>("all");
  const [topicId, setTopicId] = useState<TopicFilter>("all");
  const [topicMenuOpen, setTopicMenuOpen] = useState(false);
  const [query, setQuery] = useState("");

  const formulas = useMemo(
    () => searchPhysicsFormulas(query, level, topicId),
    [level, query, topicId],
  );
  const constants = useMemo(() => searchPhysicsConstants(query), [query]);

  const topicOptions = useMemo<SelectOption[]>(
    () => [
      { key: "all", label: t("physics.reference.all_topics") },
      ...PHYSICS_TOPICS.map(({ id, title }) => ({ key: id, label: title })),
    ],
    [t],
  );
  const activeTopic = topicOptions.find((option) => option.key === topicId)?.label ?? t("physics.reference.all_topics");

  const renderFormula = ({ item }: { item: PhysicsFormulaRow }) => <FormulaCard formula={item} />;
  const renderConstant = ({ item }: { item: PhysicsConstant }) => <ConstantCard item={item} />;
  const listHeader = tab === "formulas" ? (
    <View style={styles.listHeader}>
      <View ref={topicAnchor} collapsable={false}>
        <ListRow
          appearance="grouped"
          icon="book"
          title={t("physics.reference.topic")}
          value={activeTopic}
          accessory="chevron"
          expanded={topicMenuOpen}
          onPress={() => setTopicMenuOpen((open) => !open)}
          testID="physics-reference-topic-picker"
        />
      </View>
      <SelectMenu
        visible={topicMenuOpen}
        anchorRef={topicAnchor}
        title={t("physics.reference.topic")}
        options={topicOptions}
        selectedKey={topicId}
        onSelect={(key) => setTopicId(key)}
        onClose={() => setTopicMenuOpen(false)}
        testID="physics-reference-topic-menu"
      />
      <View style={styles.levelControl}>
        <SegmentedControl
          segments={LEVELS.map((segment) => ({
            ...segment,
            label:
              segment.key === "all" ? t("physics.reference.all_levels") : t(levelKey(segment.key)),
          }))}
          value={level}
          onChange={setLevel}
          accessibilityLabel={t("physics.reference.all_levels")}
          testID="physics-reference-level"
        />
      </View>
      <Text style={styles.resultCount} testID="physics-reference-result-count">
        {t("physics.reference.formula_count", { count: formulas.length })}
      </Text>
    </View>
  ) : (
    <Text style={styles.resultCount} testID="physics-reference-result-count">
      {t("physics.reference.formula_count", { count: constants.length })}
    </Text>
  );

  const empty = (
    <View style={styles.empty}>
      <Text style={styles.emptyText}>{t("physics.reference.no_results")}</Text>
    </View>
  );

  return (
    <View style={[styles.page, { paddingTop: insets.top + Space.sm, paddingBottom: insets.bottom }]}>
      <View style={styles.header}>
        <StackBackButton />
        <View style={styles.headingText}>
          <Text style={styles.title}>{t("physics.reference.title")}</Text>
          <Text style={styles.summary}>
            {t("physics.reference.summary", {
              formulaCount: PHYSICS_FORMULA_COUNT,
              topicCount: PHYSICS_TOPICS.length,
              constantCount: PHYSICS_CONSTANTS.length,
            })}
          </Text>
        </View>
      </View>
      <View style={styles.search}>
        <TextField
          value={query}
          onChangeText={setQuery}
          placeholder={t("physics.reference.search")}
          accessibilityLabel={t("physics.reference.search")}
          autoCorrect={false}
          autoCapitalize="none"
          returnKeyType="search"
          clearButtonMode="while-editing"
          testID="physics-reference-search"
        />
      </View>
      <View style={styles.tabs}>
        <SegmentedControl
          segments={[
            { key: "formulas", label: t("physics.reference.formulas") },
            { key: "constants", label: t("physics.reference.constants") },
          ]}
          value={tab}
          onChange={setTab}
          accessibilityLabel={t("physics.reference.title")}
          testID="physics-reference-tab"
        />
      </View>
      {tab === "formulas" ? (
        <FlatList
          data={formulas}
          keyExtractor={(item) => item.id}
          renderItem={renderFormula}
          ListHeaderComponent={listHeader}
          ListEmptyComponent={empty}
          contentContainerStyle={styles.listContent}
          keyboardShouldPersistTaps="handled"
          testID="physics-reference-formulas"
        />
      ) : (
        <FlatList
          data={constants}
          keyExtractor={(item) => item.id}
          renderItem={renderConstant}
          ListHeaderComponent={listHeader}
          ListEmptyComponent={empty}
          contentContainerStyle={styles.listContent}
          keyboardShouldPersistTaps="handled"
          testID="physics-reference-constants"
        />
      )}
    </View>
  );
}

function makeStyles(theme: ReturnType<typeof useTheme>) {
  return StyleSheet.create({
    page: { flex: 1, backgroundColor: theme.bg },
    header: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: Space.gutter,
      gap: Space.sm,
      paddingBottom: Space.sm,
    },
    headingText: { flex: 1, gap: Space.xxs },
    title: { ...Type.title, ...Weight.semibold, color: theme.text },
    summary: { ...Type.caption, color: theme.textSecondary },
    search: { paddingHorizontal: Space.gutter, paddingBottom: Space.sm },
    tabs: { paddingHorizontal: Space.gutter, paddingBottom: Space.sm },
    listHeader: { gap: Space.sm, paddingBottom: Space.sm },
    levelControl: { marginTop: Space.xxs },
    resultCount: { ...Type.caption, color: theme.textSecondary, paddingHorizontal: Space.xs },
    listContent: { paddingHorizontal: Space.gutter, paddingBottom: Space.xl, flexGrow: 1 },
    card: {
      backgroundColor: theme.surface,
      borderColor: theme.border,
      borderWidth: StyleSheet.hairlineWidth,
      borderRadius: Radius.lg,
      padding: Space.md,
      marginBottom: Space.sm,
      gap: Space.xs,
    },
    eyebrow: { ...Type.caption, color: theme.textSecondary },
    cardTitle: { ...Type.body, ...Weight.semibold, color: theme.text },
    equation: { minHeight: Space.xl, justifyContent: "center" },
    note: { ...Type.caption, color: theme.textSecondary },
    level: { ...Type.caption, color: theme.textTertiary },
    constantUnit: { ...Type.label, color: theme.textSecondary },
    empty: { flex: 1, alignItems: "center", justifyContent: "center", padding: Space.xl },
    emptyText: { ...Type.body, color: theme.textSecondary, textAlign: "center" },
  });
}
