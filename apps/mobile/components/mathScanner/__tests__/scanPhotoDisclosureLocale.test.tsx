import React from "react";
import { render } from "@testing-library/react-native";

import { MathScannerChrome } from "@/components/mathScanner/MathScannerChrome";
import { ScanReadingReview } from "@/components/mathScanner/ScanReadingReview";
import { ensureLocale } from "@/lib/i18n";
import de from "@/lib/i18n/de.json";

// The real words, in German: the line is translated, not left as English or a key.
jest.unmock("react-i18next");

const insets = { top: 47, bottom: 34, left: 0, right: 0 };
const noop = () => undefined;

beforeAll(async () => {
  await ensureLocale("de");
});
afterAll(async () => {
  await ensureLocale("en");
});

it("tells a German reader on the camera that the photo goes to Recall and AI providers", async () => {
  const view = await render(
    <MathScannerChrome
      insets={insets}
      granted
      preview={false}
      busy={false}
      torchOn={false}
      subject="physics"
      error={null}
      onClose={noop}
      onSubjectChange={noop}
      onToggleTorch={noop}
      onOpenPhotos={noop}
      onOpenFiles={noop}
      onCapture={noop}
      onRetake={noop}
      onSolve={noop}
    />,
  );
  expect(view.getByText(de["chat.math_scan_photo_disclosure"])).toBeTruthy();
});

it("tells a German reader on the review that the photo goes to Recall and AI providers", async () => {
  const view = await render(
    <ScanReadingReview
      photoUri="file:///crop.jpg"
      state={{ status: "reading" }}
      insets={insets}
      onSolve={noop}
      onSendPhoto={noop}
      onRetake={noop}
    />,
  );
  expect(view.getByText(de["chat.math_scan_photo_disclosure"])).toBeTruthy();
});
