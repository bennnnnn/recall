/** The phone's files, as the legacy file system reads and writes them. */
const mockFiles = new Map<string, string>();
jest.mock("expo-file-system/legacy", () => ({
  documentDirectory: "file:///docs/",
  getInfoAsync: jest.fn(async (path: string) => ({ exists: mockFiles.has(path) })),
  readAsStringAsync: jest.fn(async (path: string) => mockFiles.get(path) ?? ""),
  writeAsStringAsync: jest.fn(async (path: string, value: string) => {
    mockFiles.set(path, value);
  }),
  deleteAsync: jest.fn(),
}));

const FILE = "file:///docs/recall.onboarded.txt";

function load() {
  const fs = jest.requireMock<{ readAsStringAsync: jest.Mock; writeAsStringAsync: jest.Mock }>(
    "expo-file-system/legacy",
  );
  const onboarding = jest.requireActual<typeof import("@/lib/onboarding")>("@/lib/onboarding");
  return { ...onboarding, fs };
}

beforeEach(() => {
  jest.resetModules();
  mockFiles.clear();
});

it("keeps completed onboarding across module reload", async () => {
  await load().setOnboarded();
  expect(mockFiles.get(FILE)).toBe("1");
  jest.resetModules();
  await expect(load().getOnboarded()).resolves.toBe(true);
});

it("a clear takes precedence over a stored flag", async () => {
  mockFiles.set(FILE, "1");
  const first = load();
  await expect(first.getOnboarded()).resolves.toBe(true);
  await first.clearOnboarded();
  jest.resetModules();
  await expect(load().getOnboarded()).resolves.toBe(false);
});

it("does not restore a flag from a read that completes after sign-out", async () => {
  mockFiles.set(FILE, "1");
  const current = load();
  let finishRead!: (value: string) => void;
  current.fs.readAsStringAsync.mockImplementationOnce(() => new Promise((resolve) => {
    finishRead = resolve;
  }));
  const reading = current.getOnboarded();
  await current.clearOnboarded();
  finishRead("1");
  await expect(reading).resolves.toBe(false);
  expect(mockFiles.get(FILE)).toBe("0");
});

it("serializes completion and sign-out when a disk write is already pending", async () => {
  const current = load();
  let finishWrite!: () => void;
  const started = new Promise<void>((resolveStarted) => {
    current.fs.writeAsStringAsync.mockImplementationOnce(async (path: string, value: string) => {
      resolveStarted();
      await new Promise<void>((resolve) => { finishWrite = resolve; });
      mockFiles.set(path, value);
    });
  });
  const completing = current.setOnboarded();
  await started;
  const clearing = current.clearOnboarded();
  finishWrite();
  await Promise.all([completing, clearing]);
  jest.resetModules();
  await expect(load().getOnboarded()).resolves.toBe(false);
});
