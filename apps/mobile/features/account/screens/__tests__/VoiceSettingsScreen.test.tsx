import { act, fireEvent, render, waitFor } from "@testing-library/react-native";

import VoiceSettingsScreen from "@/features/account/screens/VoiceSettingsScreen";

const mockUpdateUser = jest.fn();
const mockSetSpeechRate = jest.fn();
const mockSetTtsModel = jest.fn();
let mockVoice: string | null = null;
let mockReplyVoice: string | null = null;
let mockReplyHeard = "af_heart";
let mockLocale = "en";
let mockFeatures = ["speech_tts", "live_talk"];
const mockPreviewVoice = jest.fn();

function mockUser() {
  return {
    tts_voice: mockVoice,
    reply_voice: mockReplyVoice,
    reply_voice_heard: mockReplyHeard,
    locale: mockLocale,
    features: mockFeatures,
  };
}

jest.mock("expo-router", () => ({ Redirect: () => null, useFocusEffect: () => {}, router: { push: jest.fn() } }));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "tok", user: mockUser(), updateUser: mockUpdateUser }),
  useAuthUserReader: () => () => mockUser(),
}));
jest.mock("@/features/speech/model/voicePreview", () => ({
  previewVoice: (...args: unknown[]) => mockPreviewVoice(...args),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("@/features/speech/model/speechRate", () => ({
  SPEECH_RATES: [0.75, 1, 1.25, 1.5],
  getSpeechRate: jest.fn(async () => 1.25),
  setSpeechRate: (...args: unknown[]) => mockSetSpeechRate(...args),
}));
jest.mock("@/features/speech/model/ttsPreference", () => ({
  TTS_DEVICE_MODEL: "device",
  TTS_QUALITY_MODEL: "speech-tts-model",
  getTtsModel: jest.fn(async () => "speech-tts-model"),
  setTtsModel: (...args: unknown[]) => mockSetTtsModel(...args),
}));

beforeEach(() => {
  jest.clearAllMocks();
  mockVoice = null;
  mockReplyVoice = null;
  mockReplyHeard = "af_heart";
  mockLocale = "en";
  mockFeatures = ["speech_tts", "live_talk"];
  mockUpdateUser.mockResolvedValue(undefined);
});

it("shows the default voice and this phone's saved speed", async () => {
  const view = await render(<VoiceSettingsScreen />);
  expect(view.getByLabelText("settings.voice_live, settings.voice_default")).toBeTruthy();
  expect(await view.findByLabelText("settings.voice_speed, 1.25×")).toBeTruthy();
});

it("saves a chosen live talk voice on the account", async () => {
  const view = await render(<VoiceSettingsScreen />);
  await fireEvent.press(view.getByText("settings.voice_live"));
  await fireEvent.press(view.getByLabelText("Cedar"));
  await waitFor(() => expect(mockUpdateUser).toHaveBeenCalledWith({ tts_voice: "cedar" }));
});

it("puts the server default back with Default", async () => {
  mockVoice = "sage";
  const view = await render(<VoiceSettingsScreen />);
  expect(view.getByLabelText("settings.voice_live, Sage")).toBeTruthy();
  await fireEvent.press(view.getByText("settings.voice_live"));
  await fireEvent.press(view.getByLabelText("settings.voice_default"));
  await waitFor(() => expect(mockUpdateUser).toHaveBeenCalledWith({ tts_voice: null }));
});

it("keeps speed and the on-device voice on this phone", async () => {
  const view = await render(<VoiceSettingsScreen />);
  await view.findByLabelText("settings.voice_speed, 1.25×");
  await fireEvent.press(view.getByText("settings.voice_speed"));
  await fireEvent.press(view.getByLabelText("1.5×"));
  expect(mockSetSpeechRate).toHaveBeenCalledWith(1.5);

  await act(async () => {
    fireEvent.press(view.getByRole("switch", { name: "settings.voice_on_device" }));
  });
  expect(mockSetTtsModel).toHaveBeenCalledWith("device");
  expect(mockUpdateUser).not.toHaveBeenCalled();
});

it("lists only the reply voices of the app language's model and saves the one picked", async () => {
  const view = await render(<VoiceSettingsScreen />);
  expect(view.getByLabelText("settings.voice_reply, Heart")).toBeTruthy();
  await fireEvent.press(view.getByText("settings.voice_reply"));
  // English replies play in Kokoro's voices: none of live talk's are offered.
  expect(view.queryByLabelText("Cedar")).toBeNull();
  await fireEvent.press(view.getByLabelText("George"));
  await waitFor(() => expect(mockUpdateUser).toHaveBeenCalledWith({ reply_voice: "bm_george" }));
});

it("offers tts-1's voices where it plays replies", async () => {
  mockLocale = "ru";
  mockReplyVoice = "coral";
  mockReplyHeard = "coral";
  const view = await render(<VoiceSettingsScreen />);
  expect(view.getByLabelText("settings.voice_reply, Coral")).toBeTruthy();
  await fireEvent.press(view.getByText("settings.voice_reply"));
  await fireEvent.press(view.getByLabelText("Onyx"));
  await waitFor(() => expect(mockUpdateUser).toHaveBeenCalledWith({ reply_voice: "onyx" }));
});

it("has no Same as live talk: never picked, the voice heard is ticked and named", async () => {
  // Never picked: the row names the voice heard (Heart, the first) and the menu ticks it.
  const view = await render(<VoiceSettingsScreen />);
  expect(view.getByLabelText("settings.voice_reply, Heart")).toBeTruthy();
  await fireEvent.press(view.getByText("settings.voice_reply"));
  expect(view.queryByLabelText("settings.voice_reply_follow")).toBeNull();
  await fireEvent.press(view.getByLabelText("George"));
  await waitFor(() => expect(mockUpdateUser).toHaveBeenCalledWith({ reply_voice: "bm_george" }));
});

it("says the TTS voice picked, in the engine that plays it", async () => {
  const view = await render(<VoiceSettingsScreen />);
  await fireEvent.press(view.getByText("settings.voice_reply"));
  await fireEvent.press(view.getByLabelText("George"));
  await waitFor(() => expect(mockPreviewVoice).toHaveBeenCalledWith("tok", "reply", "bm_george", "en"));
});

it("says a live talk voice picked, and nothing for Default or on a plan without it", async () => {
  const view = await render(<VoiceSettingsScreen />);
  await fireEvent.press(view.getByText("settings.voice_live"));
  await fireEvent.press(view.getByLabelText("Cedar"));
  await waitFor(() => expect(mockPreviewVoice).toHaveBeenCalledWith("tok", "live", "cedar", "en"));

  mockPreviewVoice.mockClear();
  mockVoice = "cedar";
  await view.rerender(<VoiceSettingsScreen />);
  await fireEvent.press(view.getByText("settings.voice_live"));
  await fireEvent.press(view.getByLabelText("settings.voice_default"));
  await waitFor(() => expect(mockUpdateUser).toHaveBeenCalledWith({ tts_voice: null }));
  expect(mockPreviewVoice).not.toHaveBeenCalled();

  mockFeatures = [];
  mockVoice = null;
  await view.rerender(<VoiceSettingsScreen />);
  await fireEvent.press(view.getByText("settings.voice_live"));
  await fireEvent.press(view.getByLabelText("Sage"));
  await waitFor(() => expect(mockUpdateUser).toHaveBeenCalledWith({ tts_voice: "sage" }));
  expect(mockPreviewVoice).not.toHaveBeenCalled();
});

it("ticks the voice heard when the pick is from another app language", async () => {
  // George was picked in English; the app is in Russian now, where tts-1 plays it as Ash.
  mockLocale = "ru";
  mockReplyVoice = "bm_george";
  mockReplyHeard = "ash";
  const view = await render(<VoiceSettingsScreen />);
  expect(view.getByLabelText("settings.voice_reply, Ash")).toBeTruthy();
  await fireEvent.press(view.getByText("settings.voice_reply"));
  expect(view.getByRole("radio", { name: "Ash" }).props.accessibilityState.checked).toBe(true);
});
