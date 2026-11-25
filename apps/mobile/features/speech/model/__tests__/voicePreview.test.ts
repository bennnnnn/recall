import { previewVoice, resetVoicePreviewsForTest } from "@/features/speech/model/voicePreview";

const mockVoicePreview = jest.fn();
const mockPlay = jest.fn();

jest.mock("@/features/speech/api", () => ({
  speechApi: { voicePreview: (...args: unknown[]) => mockVoicePreview(...args) },
}));
jest.mock("@/features/speech/model/pronunciation", () => ({
  playVoicePreview: (...args: unknown[]) => mockPlay(...args),
}));

beforeEach(() => {
  jest.clearAllMocks();
  resetVoicePreviewsForTest();
  mockVoicePreview.mockResolvedValue({ audio_base64: "SUQz", content_type: "audio/mpeg" });
  mockPlay.mockResolvedValue({ ok: true });
});

it("asks for a voice's clip once and plays it on every pick", async () => {
  expect(await previewVoice("tok", "reply", "af_heart", "en")).toBe(true);
  expect(await previewVoice("tok", "reply", "af_heart", "en")).toBe(true);
  expect(mockVoicePreview).toHaveBeenCalledTimes(1);
  expect(mockVoicePreview).toHaveBeenCalledWith("tok", { voice: "af_heart", kind: "reply" });
  expect(mockPlay).toHaveBeenCalledTimes(2);
  expect(mockPlay).toHaveBeenCalledWith("SUQz", "audio/mpeg");
});

it("keeps a clip per kind, voice and app language", async () => {
  await previewVoice("tok", "live", "cedar", "en");
  await previewVoice("tok", "live", "cedar", "fr");
  await previewVoice("tok", "reply", "coral", "ru");
  expect(mockVoicePreview).toHaveBeenCalledTimes(3);
});

it("plays nothing, and keeps nothing, when the server has no clip", async () => {
  mockVoicePreview.mockRejectedValueOnce(new Error("502"));
  expect(await previewVoice("tok", "reply", "af_heart", "en")).toBe(false);
  expect(mockPlay).not.toHaveBeenCalled();
  expect(await previewVoice("tok", "reply", "af_heart", "en")).toBe(true);
  expect(mockVoicePreview).toHaveBeenCalledTimes(2);
});
