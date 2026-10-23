import { deleteAsync, readDirectoryAsync } from "expo-file-system/legacy";

import { deleteAccountFiles, namedPdfFile } from "@/lib/accountFiles";

jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  deleteAsync: jest.fn(async () => undefined),
  readDirectoryAsync: jest.fn(async () => []),
}));

const listing: Record<string, string[]> = {
  "file:///cache/": ["recall-export-1.json", "other.txt"],
  "file:///cache/Print/": ["3F2A.pdf", "Spanish verbs.pdf", "Café #2.pdf", "notes.txt"],
  "file:///cache/ExpoAudio/": ["recording-1.m4a"],
};

beforeEach(() => {
  jest.clearAllMocks();
  jest.mocked(readDirectoryAsync).mockImplementation(async (dir) => listing[dir] ?? []);
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
    ].sort(),
  );
});
