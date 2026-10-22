import * as Print from "expo-print";
import { copyAsync, deleteAsync } from "expo-file-system/legacy";

import { pdfFileName, printHtmlToSharedPdf } from "@/lib/exportPdf";
import { shareLocalFile } from "@/lib/shareFile";

jest.mock("expo-print", () => ({ printToFileAsync: jest.fn() }));
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  copyAsync: jest.fn(async () => undefined),
  deleteAsync: jest.fn(async () => undefined),
  readDirectoryAsync: jest.fn(async () => []),
}));
jest.mock("@/lib/shareFile", () => ({ shareLocalFile: jest.fn(async () => undefined) }));

beforeEach(() => {
  jest.clearAllMocks();
});

it("does not open the share sheet after the requesting view expires during PDF generation", async () => {
  let resolve!: (value: { uri: string }) => void;
  (Print.printToFileAsync as jest.Mock).mockReturnValueOnce(
    new Promise((done) => {
      resolve = done;
    }),
  );
  let current = true;
  const task = printHtmlToSharedPdf("<p>Words</p>", "Spanish", () => current);
  current = false;
  resolve({ uri: "file:///cache/Print/3F2A.pdf" });
  await task;
  expect(shareLocalFile).not.toHaveBeenCalled();
  expect(deleteAsync).toHaveBeenCalledWith("file:///cache/Print/3F2A.pdf", { idempotent: true });
});

it("shares a copy named after the chat, typed as a PDF, and deletes both files after", async () => {
  (Print.printToFileAsync as jest.Mock).mockResolvedValueOnce({ uri: "file:///cache/Print/3F2A.pdf" });
  await printHtmlToSharedPdf("<p>Words</p>", "Spanish verbs", () => true);
  expect(copyAsync).toHaveBeenCalledWith({
    from: "file:///cache/Print/3F2A.pdf",
    to: "file:///cache/Print/Spanish verbs.pdf",
  });
  expect(shareLocalFile).toHaveBeenCalledWith("file:///cache/Print/Spanish verbs.pdf", {
    title: "Spanish verbs.pdf",
    mimeType: "application/pdf",
    uti: "com.adobe.pdf",
  });
  expect(deleteAsync).toHaveBeenCalledWith("file:///cache/Print/3F2A.pdf", { idempotent: true });
  expect(deleteAsync).toHaveBeenCalledWith("file:///cache/Print/Spanish verbs.pdf", {
    idempotent: true,
  });
});

it("shares the printed file when the named copy cannot be made", async () => {
  (Print.printToFileAsync as jest.Mock).mockResolvedValueOnce({ uri: "file:///cache/Print/3F2A.pdf" });
  (copyAsync as jest.Mock).mockRejectedValueOnce(new Error("disk full"));
  await printHtmlToSharedPdf("<p>Words</p>", "Spanish", () => true);
  expect(shareLocalFile).toHaveBeenCalledWith(
    "file:///cache/Print/3F2A.pdf",
    expect.objectContaining({ title: "Spanish.pdf" }),
  );
});

it.each([
  ["Spanish verbs", "Spanish verbs.pdf"],
  ["a/b: c?", "a b c.pdf"],
  ["Report.pdf", "Report.pdf"],
  ["   ", "Recall.pdf"],
  ["x".repeat(120), `${"x".repeat(80)}.pdf`],
])("names %p as %p", (title, name) => {
  expect(pdfFileName(title)).toBe(name);
});
