import React, { useLayoutEffect } from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";
import { useLessonFeedback } from "@/hooks/useLessonFeedback";
import { readPrefFile, writePrefFile } from "@/lib/filePrefs";
const mockCurrent = () => true;
const mockAudio = { start: jest.fn(), stop: jest.fn() };
const mockT = (key: string) => key;
let mockUser = "first";
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ user: { id: mockUser } }) }));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: mockT, i18n: { language: "en" } }),
}));
jest.mock("@/lib/lessonAudio", () => ({ createLessonAudio: () => mockAudio }));
jest.mock("@/lib/haptics", () => ({ notifySuccess: jest.fn(), notifyWarning: jest.fn() }));
jest.mock("@/lib/filePrefs", () => ({
  prefFilePath: (name: string) => name,
  safePrefUserId: (id: string) => id,
  readPrefFile: jest.fn(),
  writePrefFile: jest.fn(),
}));
let current: ReturnType<typeof useLessonFeedback>;
function Probe() {
  const value = useLessonFeedback(null, mockCurrent);
  useLayoutEffect(() => {
    current = value;
  });
  return <Text>{`${value.sound}:${value.voice}`}</Text>;
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
beforeEach(() => {
  jest.clearAllMocks();
  mockUser += "x";
  jest.mocked(readPrefFile).mockResolvedValue(null);
  jest.mocked(writePrefFile).mockResolvedValue(undefined);
});
it("serializes rapid preferences across visits and persists the latest toggles last", async () => {
  const pending = deferred<void>();
  jest.mocked(writePrefFile).mockReturnValueOnce(pending.promise);
  const first = await render(<Probe />);
  await act(() => {
    current.toggleSound();
    current.toggleVoice();
  });
  expect(writePrefFile).toHaveBeenCalledTimes(1);
  await first.unmount();
  await render(<Probe />);
  expect(current.sound).toBe(false);
  expect(current.voice).toBe(true);
  await act(() => current.toggleSound());
  expect(writePrefFile).toHaveBeenCalledTimes(1);
  await act(async () => {
    pending.resolve();
  });
  expect(writePrefFile).toHaveBeenCalledTimes(3);
  expect(JSON.parse(jest.mocked(writePrefFile).mock.calls[2][1])).toEqual({
    sound: true,
    voice: true,
  });
});
it("a delayed preference read cannot overwrite a newer toggle", async () => {
  const pending = deferred<string | null>();
  jest.mocked(readPrefFile).mockReturnValueOnce(pending.promise);
  await render(<Probe />);
  await act(() => current.toggleSound());
  await act(async () => pending.resolve('{"sound":true,"voice":true}'));
  expect(current.sound).toBe(false);
  expect(current.voice).toBe(false);
});
