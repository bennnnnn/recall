import * as Print from "expo-print";
import { printHtmlToSharedPdf } from "@/lib/exportPdf";
import { shareLocalFile } from "@/lib/shareFile";
jest.mock("expo-print", () => ({ printToFileAsync: jest.fn() }));
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
  resolve({ uri: "file:///example.pdf" });
  await task;
  expect(shareLocalFile).not.toHaveBeenCalled();
});
it("shares the PDF file, typed as a PDF, when the requesting view remains current", async () => {
  (Print.printToFileAsync as jest.Mock).mockResolvedValueOnce({ uri: "file:///example.pdf" });
  await printHtmlToSharedPdf("<p>Words</p>", "Spanish", () => true);
  expect(shareLocalFile).toHaveBeenCalledWith("file:///example.pdf", {
    title: "Spanish.pdf",
    mimeType: "application/pdf",
  });
});
