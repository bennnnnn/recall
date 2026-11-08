import { deleteAsync, getInfoAsync, readDirectoryAsync } from "expo-file-system/legacy";

import {
  deleteAccountFiles,
  fileInFolder,
  namedPdfFile,
  newAccountFolder,
  sweepAccountFolders,
  sweepOldPickerCopies,
} from "@/lib/accountFiles";

jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  deleteAsync: jest.fn(async () => undefined),
  getInfoAsync: jest.fn(),
  readDirectoryAsync: jest.fn(async () => []),
}));

const listing: Record<string, string[]> = {
  "file:///cache/": ["recall-export-1.json", "other.txt"],
  "file:///cache/Print/": ["3F2A.pdf", "Spanish verbs.pdf", "Café #2.pdf", "notes.txt"],
  "file:///cache/ExpoAudio/": ["recording-1.m4a"],
  "file:///cache/ImagePicker/": ["A1.jpg"],
  "file:///cache/DocumentPicker/": ["B2.pdf"],
  "file:///cache/ImageManipulator/": ["C3.jpg"],
};

const DAY_MS = 24 * 60 * 60 * 1000;
const NOW = Date.UTC(2026, 9, 23);
/** Days since each picker copy was written. */
const ageDays: Record<string, number> = {
  "file:///cache/ImagePicker/A1.jpg": 8,
  "file:///cache/DocumentPicker/B2.pdf": 2,
  "file:///cache/ImageManipulator/C3.jpg": 30,
};

beforeEach(() => {
  jest.clearAllMocks();
  jest.mocked(readDirectoryAsync).mockImplementation(async (dir) => listing[dir] ?? []);
  jest.mocked(getInfoAsync).mockImplementation(async (uri) => ({
    exists: true,
    uri,
    size: 1,
    isDirectory: false,
    // Legacy file info reports seconds.
    modificationTime: (NOW - (ageDays[uri] ?? 0) * DAY_MS) / 1000,
  }));
});

it("names a PDF with a URI iOS accepts", () => {
  expect(namedPdfFile("Spanish verbs.pdf")).toBe("file:///cache/Print/Spanish%20verbs.pdf");
});

it("sign-out deletes a named PDF by the URI it was written under", async () => {
  await deleteAccountFiles();
  const deleted = jest.mocked(deleteAsync).mock.calls.map(([uri]) => uri);
  expect(deleted.sort()).toEqual(
    [
      "file:///cache/recall-export-1.json",
      "file:///cache/Print/3F2A.pdf",
      namedPdfFile("Spanish verbs.pdf"),
      namedPdfFile("Café #2.pdf"),
      "file:///cache/ExpoAudio/recording-1.m4a",
      // Every photo and file the person picked or cropped.
      "file:///cache/ImagePicker/A1.jpg",
      "file:///cache/DocumentPicker/B2.pdf",
      "file:///cache/ImageManipulator/C3.jpg",
      // A file expo-sharing staged under its type's extension (iOS).
      "file:///cache/expo-sharing-tmp/",
    ].sort(),
  );
});

it("the launch sweep deletes only picker copies older than a week", async () => {
  await sweepOldPickerCopies(NOW);
  const deleted = jest.mocked(deleteAsync).mock.calls.map(([uri]) => uri);
  expect(deleted.sort()).toEqual(
    ["file:///cache/ImagePicker/A1.jpg", "file:///cache/ImageManipulator/C3.jpg"].sort(),
  );
});

describe("share folders", () => {
  const HOUR_MS = 60 * 60 * 1000;
  const now = Date.UTC(2026, 10, 7, 23, 0);
  const old = `recall-share-${now - 2 * HOUR_MS}-1`;
  const fresh = `recall-share-${now - 5 * 60 * 1000}-2`;
  // Made before the clock was set back two hours.
  const ahead = `recall-share-${now + 2 * HOUR_MS}-3`;

  beforeEach(() => {
    jest.spyOn(Date, "now").mockReturnValue(now);
    jest.mocked(readDirectoryAsync).mockImplementation(async (dir) =>
      dir === "file:///cache/" ? [old, fresh, ahead, "recall-export-1.json"] : [],
    );
  });
  afterEach(() => jest.restoreAllMocks());

  it("makes one folder per share under the account prefix", () => {
    expect(newAccountFolder("share")).toMatch(new RegExp(`^file:///cache/recall-share-${now}-\\d+/$`));
    expect(fileInFolder("file:///cache/recall-share-1-2/", "EduPilot model.xlsx")).toBe(
      "file:///cache/recall-share-1-2/EduPilot%20model.xlsx",
    );
  });

  it("sweeps only folders older than the age it is given; the app a file went to may still read a new one", async () => {
    await sweepAccountFolders("share", HOUR_MS);
    expect(jest.mocked(deleteAsync).mock.calls.map(([uri]) => uri)).toEqual([`file:///cache/${old}`, `file:///cache/${ahead}`]);
  });

  it("sign-out deletes every share folder, new ones too, and expo-sharing's iOS staging", async () => {
    await deleteAccountFiles();
    const deleted = jest.mocked(deleteAsync).mock.calls.map(([uri]) => uri);
    expect(deleted).toEqual(expect.arrayContaining([
      `file:///cache/${old}`, `file:///cache/${fresh}`, "file:///cache/expo-sharing-tmp/",
    ]));
  });
});
