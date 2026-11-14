/**
 * One string, one key. 49 strings sat under two or more keys (common.cancel and
 * settings.cancel, common.close and preview.close, chat.new_chat and drawer.new_chat, …):
 * each copy is translated nine times and can drift. Keys whose text is the same in every
 * language are one string unless listed here with why they must be able to differ. Keys a
 * language already words differently are apart by that language's choice.
 */
import en from "@/lib/i18n/en.json";
import am from "@/lib/i18n/am.json";
import de from "@/lib/i18n/de.json";
import es from "@/lib/i18n/es.json";
import fr from "@/lib/i18n/fr.json";
import itLocale from "@/lib/i18n/it.json";
import pt from "@/lib/i18n/pt.json";
import ru from "@/lib/i18n/ru.json";
import tr from "@/lib/i18n/tr.json";

const BUNDLES: Record<string, string>[] = [en, am, de, es, fr, itLocale, pt, ru, tr];

/** Keys with one text in every language that stay apart, and why. */
const KEPT_APART: Record<string, string> = {
  "chat.attach_file chat.title_file": "the attach sheet's row, and a chat a file opened is titled with",
  "chat.delete chat.delete_confirm_title": "an action, and the title of the dialog it opens",
  "chat.email_card_subject chat.email_card_subject_placeholder": "a field's label, and its placeholder",
  "chat.live_talk_a11y upgrade.feature_live_talk_plain": "the call button and a plan feature",
  "chat.status.answer_photo chat.status.finding_photo": "a status line per step, named by its id",
  "chat.status.chemistry_1 chat.status.physics_1": "each subject's own steps",
  "chat.status.chemistry_2 chat.status.physics_2": "each subject's own steps",
  "common.delete todos.proposal_delete": "the Delete action, and a to-do card named by its kind",
  "common.you memory.group.you share.role_user": "the profile, a memory group named by its id, a transcript speaker",
  "drawer.reminders notifications.todo_reminder_title": "the drawer's row, and a reminder notification's title",
  "drawer.today picker.today settings.usage_today": "the drawer's day heading, the date picker's button, a usage row",
  "memory.doc.profile.title settings.profile": "a memory page named by its id, and a Settings page",
  "memory.title settings.memory": "the Memory screen, and Settings → Memory",
  "money.term_months money.term_years": "a loan's term in months, and in years",
  "onboarding.consent_search_title settings.web_search": "a consent item, and a Settings row",
  "onboarding.consent_voice_title settings.voice": "a consent item, and a Settings page",
  "rich.diagram_title_wave rich.scene_title_wave": "a diagram and a scene, each named by its kind",
  "settings.appearance settings.field_appearance": "a Settings row, and a field a settings card names by its id",
  "settings.chat share.default_title": "a Settings section, and a shared chat's default title",
  "todos.group_today todos.menu_today": "a to-do group named by its id, and the view menu's item",
  "todos.proposal_done_move todos.proposal_done_set_due": "a to-do card per change, named by its kind",
  "todos.proposal_move todos.proposal_set_due": "a to-do card per change, named by its kind",
};

/** Groups of keys whose text is the same in every language, each as its keys in order. */
function sameEverywhere(): string[] {
  const byText = new Map<string, string[]>();
  for (const key of Object.keys(en)) {
    const texts = BUNDLES.map((bundle) => bundle[key]).join("\u0000");
    byText.set(texts, [...(byText.get(texts) ?? []), key]);
  }
  return [...byText.values()].filter((keys) => keys.length > 1).map((keys) => keys.sort().join(" "));
}

describe("i18n duplicates", () => {
  it("keeps one key for a string every language words the same", () => {
    const merge = sameEverywhere().filter((group) => !(group in KEPT_APART));
    expect(merge).toEqual([]);
  });

  it("lists only groups that are still the same everywhere", () => {
    const groups = new Set(sameEverywhere());
    expect(Object.keys(KEPT_APART).filter((group) => !groups.has(group))).toEqual([]);
  });
});
