import { useState } from "react";
import { useTranslation } from "react-i18next";

import { SettingsFieldSheet } from "@/features/account/components/SettingsFieldSheet";
import {
  SettingsGroup,
  SettingsLinkRow,
  SettingsMenuRow,
  SettingsPage,
  useSettingsAction,
} from "@/features/account/components/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import {
  DEFAULT_RESPONSE_TONE,
  normalizeResponseTone,
  RESPONSE_TONE_ORDER,
} from "@/lib/responseTone";

const STYLES = ["short", "balanced", "detailed"] as const;
type ResponseStyle = (typeof STYLES)[number];

function normalizeStyle(raw: string | undefined): ResponseStyle {
  return STYLES.find((style) => style === raw) ?? "balanced";
}

/** Settings → Personalization: how replies sound. */
export default function PreferencesSettingsScreen() {
  const { user, updateUser } = useAuth();
  const { t } = useTranslation();
  const action = useSettingsAction();
  const [instructionsOpen, setInstructionsOpen] = useState(false);
  const [instructionsText, setInstructionsText] = useState("");

  const selectedStyle = normalizeStyle(user?.response_style);
  const selectedTone = normalizeResponseTone(user?.response_tone ?? DEFAULT_RESPONSE_TONE);
  const saving = action.busy !== null;

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
            title={t("settings.style")}
            value={t(`settings.style_${selectedStyle}`)}
            options={STYLES.map((key) => ({ key, label: t(`settings.style_${key}`) }))}
            selectedKey={selectedStyle}
            disabled={saving}
            busy={action.busy === "style"}
            onSelect={(style) =>
              void action.run("style", () => updateUser({ response_style: style }))
            }
          />
          <SettingsMenuRow
            title={t("settings.tone")}
            value={t(`settings.tone_${selectedTone}`)}
            options={RESPONSE_TONE_ORDER.map((key) => ({ key, label: t(`settings.tone_${key}`) }))}
            selectedKey={selectedTone}
            disabled={saving}
            busy={action.busy === "tone"}
            onSelect={(tone) =>
              void action.run("tone", () => updateUser({ response_tone: tone }))
            }
          />
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

      <SettingsFieldSheet
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
