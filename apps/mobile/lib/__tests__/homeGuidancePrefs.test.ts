jest.mock("@/lib/filePrefs", () => ({
  prefFilePath: (name: string) => `file:///docs/${name}`,
  readPrefFile: jest.fn(),
  safePrefUserId: (id: string) => id.replace(/[^a-zA-Z0-9._-]/g, "_"),
  writePrefFile: jest.fn(),
}));

beforeEach(() => jest.resetModules());

function load(stored: { value: string | null }) {
  const prefs = jest.requireMock("@/lib/filePrefs");
  prefs.readPrefFile.mockImplementation(async () => stored.value);
  prefs.writePrefFile.mockImplementation(async (_path: string, value: string) => {
    stored.value = value;
  });
  const guidance = jest.requireActual<typeof import("@/lib/homeGuidancePrefs")>(
    "@/lib/homeGuidancePrefs",
  );
  return { ...guidance, prefs };
}

it("shows guidance until the account uses chat, then keeps it retired", async () => {
  const stored = { value: null as string | null };
  const guidance = load(stored);
  await expect(guidance.isHomeGuidanceRetired("user/1")).resolves.toBe(false);

  await guidance.retireHomeGuidance("user/1");
  expect(stored.value).toBe("1");
  await expect(guidance.isHomeGuidanceRetired("user/1")).resolves.toBe(true);
  expect(guidance.prefs.writePrefFile).toHaveBeenCalledWith(
    "file:///docs/recall.home-guidance.user_1.txt",
    "1",
  );
});

it("does not revive guidance when a disk read finishes after retirement", async () => {
  const stored = { value: null as string | null };
  const guidance = load(stored);
  let finishRead!: (value: string | null) => void;
  guidance.prefs.readPrefFile.mockImplementationOnce(
    () => new Promise((resolve) => { finishRead = resolve; }),
  );

  const reading = guidance.isHomeGuidanceRetired("user-2");
  await guidance.retireHomeGuidance("user-2");
  finishRead(null);

  await expect(reading).resolves.toBe(true);
  await expect(guidance.isHomeGuidanceRetired("user-2")).resolves.toBe(true);
});
