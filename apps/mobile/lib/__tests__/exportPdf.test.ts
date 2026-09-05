import { Share } from "react-native";
import * as Print from "expo-print";
import { printHtmlToSharedPdf } from "@/lib/exportPdf";
jest.mock("react-native", () => ({
  Share: { share: jest.fn(), sharedAction: "sharedAction", dismissedAction: "dismissedAction" },
}));
jest.mock("expo-print", () => ({ printToFileAsync: jest.fn() }));
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
  const share = jest.spyOn(Share, "share").mockResolvedValue({ action: Share.sharedAction });
  let current = true;
  const task = printHtmlToSharedPdf("<p>Words</p>", "Spanish", () => current);
  current = false;
  resolve({ uri: "file:///example.pdf" });
  await task;
  expect(share).not.toHaveBeenCalled();
});
it("shares a PDF when the requesting view remains current", async () => {
  (Print.printToFileAsync as jest.Mock).mockResolvedValueOnce({ uri: "file:///example.pdf" });
  const share = jest.spyOn(Share, "share").mockResolvedValue({ action: Share.sharedAction });
  await printHtmlToSharedPdf("<p>Words</p>", "Spanish", () => true);
  expect(share).toHaveBeenCalledWith({ url: "file:///example.pdf", title: "Spanish.pdf" });
});
