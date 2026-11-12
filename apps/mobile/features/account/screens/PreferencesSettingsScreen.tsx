import { useState } from "react";
import { useTranslation } from "react-i18next";

import { FieldSheet } from "@/ui/overlay/FieldSheet";
import {
  SettingsGroup,
  SettingsLinkRow,
  SettingsMenuRow,
  SettingsPage,
  SettingsSwitchRow,
  useSettingSave,
  useSettingsAction,
} from "@/features/account/components/settingsUi";
import { useHaptics } from "@/contexts/AppearanceContext";
import { useAuth } from "@/contexts/AuthContext";
import {
  DEFAULT_RESPONSE_TONE,
  EMOJI_USE_ORDER,
  normalizeEmojiUse,
  normalizeResponseTone,
  RESPONSE_TONE_ORDER,
} from "@/lib/responseTone";

/** Settings → Personalization: how replies sound and how many emoji they use. Length follows each message
 * ("briefly", "in detail"); there is no account-wide length setting. */
export default function PreferencesSettingsScreen() {
  const { user, updateUser } = useAuth();
  const { t } = useTranslation();
  const action = useSettingsAction();
  const save = useSettingSave();
  const haptics = useHaptics();
  const [instructionsOpen, setInstructionsOpen] = useState(false);
  const [instructionsText, setInstructionsText] = useState("");

  const selectedTone = normalizeResponseTone(user?.response_tone ?? DEFAULT_RESPONSE_TONE);
  const selectedEmoji = normalizeEmojiUse(user?.emoji_use);

  const openInstructions = () => {
    setInstructionsText(user?.custom_instructions ?? "");
    setInstructionsOpen(true);
  };

  const saveInstructions = async () => {
    const trimmed = instructionsText.trim() || null;
    if ((user?.custom_instructions ?? null) === trimmed) {
      setInstructionsOpen(false);
      return;
    }
    const saved = await action.run("instructions", () =>
      updateUser({ custom_instructions: trimmed }),
    );
    if (saved) setInstructionsOpen(false);
  };

  return (
    <>
      <SettingsPage>
        <SettingsGroup label={t("settings.chat")}>
          <SettingsMenuRow
            title={t("settings.tone")}
            value={t(`settings.tone_${selectedTone}`)}
            options={RESPONSE_TONE_ORDER.map((key) => ({ key, label: t(`settings.tone_${key}`) }))}
            selectedKey={selectedTone}
            onSelect={(tone) => save({ response_tone: tone })}
          />
          <SettingsMenuRow
            title={t("settings.emoji")}
            value={t(`settings.emoji_${selectedEmoji}`)}
            options={EMOJI_USE_ORDER.map((key) => ({ key, label: t(`settings.emoji_${key}`) }))}
            selectedKey={selectedEmoji}
            onSelect={(level) => save({ emoji_use: level })}
          />
          <SettingsSwitchRow
            title={t("settings.follow_up_suggestions")}
            value={user?.follow_up_suggestions_enabled !== false}
            onValueChange={(next) => save({ follow_up_suggestions_enabled: next })}
          />
        </SettingsGroup>
        <SettingsGroup>
          <SettingsSwitchRow
            icon="vibrate"
            title={t("settings.haptics")}
            value={haptics.enabled}
            onValueChange={(next) => void haptics.setEnabled(next)}
          />
        </SettingsGroup>
        <SettingsGroup>
          <SettingsLinkRow
            title={t("settings.custom_instructions")}
            value={
              user?.custom_instructions?.trim()
                ? t("settings.on")
                : t("settings.custom_instructions_none")
            }
            onPress={openInstructions}
          />
        </SettingsGroup>
      </SettingsPage>

      <FieldSheet
        visible={instructionsOpen}
        title={t("settings.custom_instructions")}
        hint={t("settings.custom_instructions_hint")}
        value={instructionsText}
        onChangeText={setInstructionsText}
        onClose={() => setInstructionsOpen(false)}
        onSave={() => void saveInstructions()}
        saving={action.busy === "instructions"}
        multiline
        maxLength={1000}
        placeholder={t("settings.custom_instructions_placeholder")}
      />
    </>
  );
}
