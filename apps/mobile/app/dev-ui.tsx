import { useMemo, useRef, useState, type ReactNode } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useAppearance } from "@/contexts/AppearanceContext";
import type { AppearancePreference } from "@/lib/appearance";
import { formatClockTime, formatMonthDayYear } from "@/lib/datetime/format";
import { timeFromDate, withTimeOfDay } from "@/lib/datetime/clockDial";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { Button } from "@/ui/controls/Button";
import { Chip } from "@/ui/controls/Chip";
import { HeaderButton, HeaderButtonGroup } from "@/ui/controls/HeaderButton";
import { SegmentedControl } from "@/ui/controls/SegmentedControl";
import { TextField } from "@/ui/controls/TextField";
import { CountBadge } from "@/ui/feedback/CountBadge";
import { StateView } from "@/ui/feedback/StateView";
import { StatusPill } from "@/ui/feedback/StatusPill";
import { BrandMark } from "@/ui/icons/brand";
import { CUSTOM_GLYPHS } from "@/ui/icons/custom";
import { GLYPHS } from "@/ui/icons/glyphs.generated";
import { Icon } from "@/ui/icons/Icon";
import type { IconName } from "@/ui/icons/names";
import { IconSize } from "@/ui/icons/sizes";
import { ListGroup, ListSeparator } from "@/ui/list/ListGroup";
import { ListRow } from "@/ui/list/ListRow";
import { alertDialog, confirmDialog } from "@/ui/overlay/dialogs";
import { Menu } from "@/ui/overlay/Menu";
import { SelectMenu } from "@/ui/overlay/SelectMenu";
import { DatePickerDialog } from "@/ui/pickers/DatePickerDialog";
import { DateTimePickerDialog } from "@/ui/pickers/DateTimePickerDialog";
import { TimePickerDialog } from "@/ui/pickers/TimePickerDialog";
import { ShareSheet } from "@/ui/share/ShareSheet";

const ICON_NAMES = [...Object.keys(GLYPHS), ...Object.keys(CUSTOM_GLYPHS)].sort() as IconName[];
const APPEARANCE = [
  { key: "system", label: "System" },
  { key: "light", label: "Light" },
  { key: "dark", label: "Dark" },
] as const;
const TONES = [
  { key: "warm", label: "Warm" },
  { key: "neutral", label: "Neutral" },
  { key: "direct", label: "Direct" },
];

/**
 * Development builds only: every UI kit piece on one screen, to review in
 * light and dark on a phone. Production builds redirect home.
 */
export default function DevUiGallery() {
  if (!__DEV__) return <Redirect href="/" />;
  return <Gallery />;
}

function Gallery() {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const feedback = useActionFeedbackOptional();
  const { preference, setPreference } = useAppearance();

  const [switchOn, setSwitchOn] = useState(true);
  const [filter, setFilter] = useState("all");
  const [size, setSize] = useState<"small" | "medium" | "large">("medium");
  const [skills, setSkills] = useState(["Python", "Figma", "SQL"]);
  const [name, setName] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [toneOpen, setToneOpen] = useState(false);
  const [tone, setTone] = useState("warm");
  const [picker, setPicker] = useState<"time" | "date" | "both" | null>(null);
  const [shareOpen, setShareOpen] = useState(false);
  const [when, setWhen] = useState(() => new Date());
  const menuRef = useRef<View>(null);
  const toneRef = useRef<View>(null);

  return (
    <View style={[s.root, { paddingTop: insets.top }]}>
      <View style={s.header}>
        <HeaderButton
          icon="arrow-left"
          variant="plain"
          accessibilityLabel="Back"
          onPress={() => router.back()}
        />
        <Text style={s.headerTitle}>UI kit</Text>
        <HeaderButton
          ref={menuRef}
          icon="more-vertical"
          accessibilityLabel="Menu"
          onPress={() => setMenuOpen(true)}
        />
      </View>

      <ScrollView contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.xl }]}>
        <SegmentedControl
          segments={APPEARANCE}
          value={preference}
          onChange={(next) => void setPreference(next as AppearancePreference)}
          accessibilityLabel="Appearance"
        />

        <Section title="Buttons">
          <Button title="Primary" onPress={() => undefined} />
          <Button title="Outline" variant="outline" onPress={() => undefined} />
          <Button title="Ghost" variant="ghost" onPress={() => undefined} />
          <Button title="Delete" variant="destructive" onPress={() => undefined} />
          <View style={s.row}>
            <Button title="Small" size="sm" onPress={() => undefined} />
            <Button title="Saving" loading onPress={() => undefined} />
          </View>
          <Button title="Get started" size="lg" icon="arrow-right" iconPlacement="end" onPress={() => undefined} />
        </Section>

        <Section title="Chips">
          <View style={s.wrap}>
            <Chip label="Plan my week" icon="sparkles" onPress={() => undefined} />
            <Chip label="Explain like I'm new" icon="lightbulb" onPress={() => undefined} />
          </View>
          <View style={s.wrap}>
            {["all", "photos", "files"].map((key) => (
              <Chip
                key={key}
                variant="filter"
                accessibilityRole="radio"
                label={key[0].toUpperCase() + key.slice(1)}
                selected={filter === key}
                onPress={() => setFilter(key)}
              />
            ))}
          </View>
          <View style={s.wrap}>
            {skills.map((skill) => (
              <Chip
                key={skill}
                variant="input"
                label={skill}
                removeLabel={`Remove ${skill}`}
                onRemove={() => setSkills((list) => list.filter((item) => item !== skill))}
              />
            ))}
          </View>
          <View style={s.wrap}>
            <Chip variant="tag" icon="map-pin" prefix="Where:" label="Berlin" />
            <Chip variant="tag" icon="briefcase" label="Hybrid" />
            <StatusPill label="New" />
            <CountBadge count={7} />
          </View>
        </Section>

        <Section title="Segmented control">
          <SegmentedControl
            segments={[
              { key: "small", label: "Small" },
              { key: "medium", label: "Medium" },
              { key: "large", label: "Large" },
            ]}
            value={size}
            onChange={setSize}
            accessibilityLabel="Text size"
          />
        </Section>

        <Section title="Rows">
          <ListGroup label="Grouped">
            <ListRow
              ref={toneRef}
              icon="sparkles"
              title="Tone"
              value={TONES.find((item) => item.key === tone)?.label}
              onPress={() => setToneOpen(true)}
            />
            <ListSeparator />
            <ListRow icon="bell" title="Reminders" subtitle="Before each to-do" switchValue={switchOn} onSwitchChange={setSwitchOn} />
            <ListSeparator />
            <ListRow icon="cloud-off" title="Syncing" busy onPress={() => undefined} />
            <ListSeparator />
            <ListRow icon="trash" title="Delete all chats" danger onPress={() => undefined} />
          </ListGroup>
          <View style={s.plainGroup}>
            <ListRow
              appearance="plain"
              icon="calendar"
              title="Date"
              detail={formatMonthDayYear(when)}
              detailStyle="pill"
              onPress={() => setPicker("date")}
            />
            <ListRow
              appearance="plain"
              icon="clock"
              title="Time"
              detail={formatClockTime(when)}
              detailStyle="pill"
              onPress={() => setPicker("time")}
            />
            <ListRow appearance="plain" icon="images" title="Library" accessory="chevron" onPress={() => undefined} />
          </View>
        </Section>

        <Section title="Text fields">
          <TextField label="Name" placeholder="What should Recall call you?" value={name} onChangeText={setName} />
          <TextField label="Salary" value="12k" error="Enter a yearly amount in numbers." />
          <TextField label="Notes" helper="Only you can see this." multiline />
        </Section>

        <Section title="Header buttons">
          <View style={s.row}>
            <HeaderButton icon="menu" accessibilityLabel="Menu" onPress={() => undefined} />
            <HeaderButton icon="close" accessibilityLabel="Close" onPress={() => undefined} />
            <HeaderButtonGroup>
              <HeaderButton variant="plain" icon="edit" accessibilityLabel="New chat" onPress={() => undefined} />
              <HeaderButton variant="plain" icon="more-vertical" accessibilityLabel="More" onPress={() => undefined} />
            </HeaderButtonGroup>
          </View>
          <View style={[s.row, s.media]}>
            <HeaderButton variant="media" icon="close" accessibilityLabel="Close" onPress={() => undefined} />
            <HeaderButton variant="media" icon="share" accessibilityLabel="Share" onPress={() => undefined} />
            <HeaderButton variant="media" icon="download" busy accessibilityLabel="Download" onPress={() => undefined} />
          </View>
        </Section>

        <Section title="Popups">
          <Button title="Menu" variant="outline" onPress={() => setMenuOpen(true)} />
          <Button
            title="Confirm dialog"
            variant="outline"
            onPress={() =>
              void confirmDialog({
                title: "Delete this chat?",
                message: "This can't be undone.",
                confirmLabel: "Delete",
                destructive: true,
              }).then((ok) => feedback?.info(ok ? "Deleted" : "Kept"))
            }
          />
          <Button
            title="Notice"
            variant="outline"
            onPress={() => void alertDialog({ title: "Saved", message: "Image saved to your photos." })}
          />
          <View style={s.row}>
            <Button title="Toast" variant="outline" size="sm" onPress={() => feedback?.success("Chat archived")} />
            <Button title="Error toast" variant="outline" size="sm" onPress={() => feedback?.error("Could not save")} />
          </View>
          <Button title="Share sheet" variant="outline" onPress={() => setShareOpen(true)} />
          <View style={s.row}>
            <Button title="Time" variant="outline" size="sm" onPress={() => setPicker("time")} />
            <Button title="Date" variant="outline" size="sm" onPress={() => setPicker("date")} />
            <Button title="Date + time" variant="outline" size="sm" onPress={() => setPicker("both")} />
          </View>
        </Section>

        <Section title="States">
          <StateView variant="empty" icon="folder-open" title="Nothing here yet" />
          <StateView variant="error" title="Could not load" onRetry={() => undefined} />
        </Section>

        <Section title={`Icons (${ICON_NAMES.length})`}>
          <View style={s.brands}>
            {(["google", "gmail", "apple", "x", "linkedin", "facebook", "instagram"] as const).map((brand) => (
              <BrandMark key={brand} name={brand} size={IconSize.lg} />
            ))}
          </View>
          <View style={s.icons}>
            {ICON_NAMES.map((iconName) => (
              <View key={iconName} style={s.iconCell}>
                <Icon name={iconName} size={IconSize.md} />
                <Text style={s.iconName} numberOfLines={1}>
                  {iconName}
                </Text>
              </View>
            ))}
          </View>
        </Section>
      </ScrollView>

      <Menu
        visible={menuOpen}
        anchorRef={menuRef}
        onClose={() => setMenuOpen(false)}
        items={[
          { key: "share", icon: "share", label: "Share", onPress: () => setShareOpen(true) },
          { key: "rename", icon: "edit", label: "Rename", onPress: () => undefined },
          { key: "pin", icon: "pin", label: "Pin", onPress: () => undefined },
          "separator",
          { key: "delete", icon: "trash", label: "Delete", destructive: true, onPress: () => undefined },
        ]}
      />
      <SelectMenu
        visible={toneOpen}
        anchorRef={toneRef}
        title="Tone"
        options={TONES}
        selectedKey={tone}
        onSelect={setTone}
        onClose={() => setToneOpen(false)}
      />
      <TimePickerDialog
        visible={picker === "time"}
        value={timeFromDate(when)}
        onConfirm={(time) => {
          setWhen(withTimeOfDay(when, time));
          setPicker(null);
        }}
        onCancel={() => setPicker(null)}
      />
      <DatePickerDialog
        visible={picker === "date"}
        value={when}
        onConfirm={(date) => {
          setWhen(date);
          setPicker(null);
        }}
        onCancel={() => setPicker(null)}
      />
      <DateTimePickerDialog
        visible={picker === "both"}
        value={when}
        onConfirm={(date) => {
          setWhen(date);
          setPicker(null);
        }}
        onCancel={() => setPicker(null)}
      />
      <ShareSheet
        visible={shareOpen}
        onClose={() => setShareOpen(false)}
        heading="Share chat"
        note="Shares a copy of this chat as it is now."
        preview={{ title: "Weekend trip to Lisbon", meta: "Recall · Sep 26, 2026", icon: "message" }}
        load={async () => "# Weekend trip to Lisbon\n\nYou: Plan two days in Lisbon."}
        autoShare={false}
        onExportPdf={async () => undefined}
        labels={{
          share: "Share",
          copy: "Copy",
          copied: "Copied",
          pdf: "PDF",
          copyText: "Copy text",
          failed: { share: "Could not share", copy: "Could not copy", pdf: "Could not make the PDF" },
        }}
      />
    </View>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <View style={s.section}>
      <Text style={s.sectionTitle} accessibilityRole="header">
        {title}
      </Text>
      {children}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: t.bg },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xs,
    },
    headerTitle: { ...Type.navTitle, color: t.text },
    content: { padding: Space.md, gap: Space.lg },
    section: { gap: Space.sm },
    sectionTitle: { ...Type.overline, color: t.textTertiary },
    row: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: Space.xs },
    wrap: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: Space.xs },
    plainGroup: { paddingHorizontal: Space.xs },
    media: {
      padding: Space.sm,
      borderRadius: Radius.lg,
      backgroundColor: t.mediaScrim,
    },
    brands: { flexDirection: "row", flexWrap: "wrap", gap: Space.md },
    icons: { flexDirection: "row", flexWrap: "wrap" },
    iconCell: { width: "25%", alignItems: "center", gap: Space.xxs, paddingVertical: Space.xs },
    iconName: { ...Type.caption, color: t.textSecondary },
  });
}
