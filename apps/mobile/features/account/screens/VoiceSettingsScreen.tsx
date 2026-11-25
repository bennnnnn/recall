import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  SettingsGroup,
  SettingsMenuRow,
  SettingsPage,
  SettingsSwitchRow,
  useSettingsAction,
} from "@/features/account/components/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import {
  getSpeechRate,
  setSpeechRate,
  SPEECH_RATES,
  type SpeechRate,
} from "@/features/speech/model/speechRate";
import {
  getTtsModel,
  setTtsModel,
  TTS_DEVICE_MODEL,
  TTS_QUALITY_MODEL,
} from "@/features/speech/model/ttsPreference";
import {
  replyVoiceLabel,
  replyVoicesFor,
  USER_VOICES,
  voiceLabel,
} from "@/features/speech/model/voices";
import { numberFormat } from "@/lib/money/format";

const DEFAULT_VOICE = "default";
// The Reply voice menu's row that saves null: the reply follows the live talk voice.
const FOLLOW_LIVE_VOICE = "follow";

/**
 * Settings → Voice. Two voices are saved on the account: live talk's, and the one a reply
 * plays in when the user taps Listen (only the voices of the model that plays replies in the
 * app's language, so the voice picked is the voice heard). Speed and the on-device voice are
 * this phone's.
 */
export default function VoiceSettingsScreen() {
  const { user, updateUser } = useAuth();
  const { t, i18n } = useTranslation();
  const action = useSettingsAction();
  const [rate, setRate] = useState<SpeechRate>(1);
  const [onDevice, setOnDevice] = useState(false);

  useEffect(() => {
    let active = true;
    void Promise.all([getSpeechRate(), getTtsModel()]).then(([savedRate, model]) => {
      if (!active) return;
      setRate(savedRate);
      setOnDevice(model === TTS_DEVICE_MODEL);
    });
    return () => {
      active = false;
    };
  }, []);

  const voiceOptions = useMemo(
    () => [
      { key: DEFAULT_VOICE, label: t("settings.voice_default") },
      ...USER_VOICES.map((voice) => ({ key: voice, label: voiceLabel(voice) })),
    ],
    [t],
  );
  const rateLabel = useMemo(() => {
    const format = numberFormat(i18n.language);
    return (value: number) => `${format.format(value)}×`;
  }, [i18n.language]);
  const rateOptions = SPEECH_RATES.map((value) => ({
    key: String(value),
    label: rateLabel(value),
  }));

  const voice = user?.tts_voice ?? null;

  return (
    <SettingsPage>
      <SettingsGroup>
        <ReplyVoiceRow action={action} />
        <SettingsMenuRow
          title={t("settings.voice_live")}
          subtitle={t("settings.voice_choice_summary")}
          value={voice ? voiceLabel(voice) : t("settings.voice_default")}
          options={voiceOptions}
          selectedKey={voice ?? DEFAULT_VOICE}
          busy={action.busy === "voice"}
          onSelect={(key) => {
            const next = USER_VOICES.find((candidate) => candidate === key) ?? null;
            void action.run("voice", () => updateUser({ tts_voice: next }));
          }}
        />
        <SettingsMenuRow
          title={t("settings.voice_speed")}
          subtitle={t("settings.voice_speed_summary")}
          value={rateLabel(rate)}
          options={rateOptions}
          selectedKey={String(rate)}
          onSelect={(key) => {
            const next = SPEECH_RATES.find((value) => String(value) === key);
            if (next === undefined) return;
            setRate(next);
            void setSpeechRate(next);
          }}
        />
      </SettingsGroup>

      <SettingsGroup>
        <SettingsSwitchRow
          title={t("settings.voice_on_device")}
          subtitle={t("settings.voice_on_device_summary")}
          value={onDevice}
          onValueChange={(next) => {
            setOnDevice(next);
            void setTtsModel(next ? TTS_DEVICE_MODEL : TTS_QUALITY_MODEL);
          }}
        />
      </SettingsGroup>
    </SettingsPage>
  );
}

/**
 * Reply voice: "Follow live talk voice" (saves null), then the voices of the model that plays
 * replies in the app's language. The pick ticks its row; the row names the voice heard.
 */
function ReplyVoiceRow({ action }: { action: ReturnType<typeof useSettingsAction> }) {
  const { user, updateUser } = useAuth();
  const { t } = useTranslation();
  const replyVoices = replyVoicesFor(user?.locale);
  const options = useMemo(
    () => [
      { key: FOLLOW_LIVE_VOICE, label: t("settings.voice_reply_follow") },
      ...replyVoices.map((voice) => ({ key: voice.id, label: replyVoiceLabel(voice.id) })),
    ],
    [replyVoices, t],
  );
  const heard = user?.reply_voice_heard ?? null;
  return (
    <SettingsMenuRow
      title={t("settings.voice_reply")}
      subtitle={t("settings.voice_reply_summary")}
      value={heard ? replyVoiceLabel(heard) : t("settings.voice_default")}
      options={options}
      selectedKey={user?.reply_voice ?? FOLLOW_LIVE_VOICE}
      busy={action.busy === "reply_voice"}
      onSelect={(key) => {
        const next = key === FOLLOW_LIVE_VOICE ? null : key;
        if (next && !replyVoices.some((candidate) => candidate.id === next)) return;
        void action.run("reply_voice", () => updateUser({ reply_voice: next }));
      }}
    />
  );
}
