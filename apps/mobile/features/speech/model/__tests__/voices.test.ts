/**
 * docs/fixtures/reply_voices.json holds the Reply voice picker by app language, and the
 * API's test (test_listen_routing.py) holds the server's voice catalog to the same lists: the
 * voice the phone offers is one the model that plays the reply really has.
 */
import fixture from "../../../../../../docs/fixtures/reply_voices.json";
import {
  heardVoiceLabel,
  listenVoiceKey,
  replyVoiceLabel,
  replyVoicesFor,
  REPLY_VOICES,
} from "@/features/speech/model/voices";
import { LANGUAGES } from "@/lib/i18n/languages";

type Voice = { id: string; female: boolean };
const DATA = fixture as unknown as { languages: Record<string, Voice[] | "openai">; openai: Voice[] };

function expectedFor(code: string): Voice[] {
  const listed = DATA.languages[code];
  return listed === "openai" ? DATA.openai : (listed ?? []);
}

it.each(LANGUAGES.map((language) => language.code))(
  "lists %s's reply voices as the server does",
  (code) => {
    expect(REPLY_VOICES[code]).toEqual(expectedFor(code));
    expect(replyVoicesFor(`${code}-XX`)).toEqual(expectedFor(code));
  },
);

it("falls back to English's voices for a language it lacks", () => {
  expect(replyVoicesFor("de")).toEqual(expectedFor("en"));
  expect(replyVoicesFor(null)).toEqual(expectedFor("en"));
});

it("names a voice without its language and gender prefix", () => {
  expect(replyVoiceLabel("af_heart")).toBe("Heart");
  expect(replyVoiceLabel("bm_george")).toBe("George");
  expect(replyVoiceLabel("coral")).toBe("Coral");
});

it("keys a reply's clips on both voices, so a change of either asks anew", () => {
  expect(listenVoiceKey({ reply_voice: "af_heart", tts_voice: "sage" })).toBe("af_heart|sage");
  expect(listenVoiceKey({ reply_voice: null, tts_voice: "coral" })).toBe("|coral");
  expect(listenVoiceKey({ reply_voice: null, tts_voice: null })).toBeNull();
});

it("names the voice heard, or the live talk voice from an older server", () => {
  expect(heardVoiceLabel({ reply_voice_heard: "am_michael", tts_voice: "cedar" })).toBe("Michael");
  expect(heardVoiceLabel({ tts_voice: "cedar" })).toBe("Cedar");
  expect(heardVoiceLabel(null)).toBeNull();
});
