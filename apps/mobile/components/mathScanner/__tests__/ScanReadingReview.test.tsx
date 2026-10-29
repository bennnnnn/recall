import React from "react";
import { act, fireEvent, render } from "@testing-library/react-native";

import { ScanReadingReview, type ScanReadingState } from "@/components/mathScanner/ScanReadingReview";
import { lightTheme as mockLightTheme } from "@/lib/theme";
import { DYNAMIC_TYPE_MAX } from "@/lib/type";

jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));

const insets = { top: 47, bottom: 34, left: 0, right: 0 };

async function renderReview(state: ScanReadingState) {
  const onSolve = jest.fn();
  const onSendPhoto = jest.fn();
  const onRetake = jest.fn();
  const view = await render(
    <ScanReadingReview
      photoUri="file:///crop.jpg"
      state={state}
      insets={insets}
      onSolve={onSolve}
      onSendPhoto={onSendPhoto}
      onRetake={onRetake}
    />,
  );
  return { ...view, onSolve, onSendPhoto, onRetake };
}

describe("ScanReadingReview", () => {
  it("shows the reading to edit and solves the edited text", async () => {
    const view = await renderReview({ status: "ready", reading: "2x + 3 = 7", uncertain: false });
    const field = view.getByTestId("math-scan-reading");
    expect(field.props.value).toBe("2x + 3 = 7");
    await act(async () => {
      fireEvent.changeText(field, "2x + 3 = 11 ");
    });
    await act(async () => {
      fireEvent.press(view.getByText("chat.math_scan_solve"));
    });
    expect(view.onSolve).toHaveBeenCalledWith("2x + 3 = 11");
    expect(view.queryByText("chat.math_scan_uncertain")).toBeNull();
  });

  it("asks for a closer look when the read was uncertain", async () => {
    const view = await renderReview({ status: "ready", reading: "2x + 3 = 7", uncertain: true });
    expect(view.getByText("chat.math_scan_uncertain")).toBeTruthy();
  });

  it("lets the photo go without waiting for the read", async () => {
    const view = await renderReview({ status: "reading" });
    expect(view.getByText("chat.math_scan_reading")).toBeTruthy();
    expect(view.queryByTestId("math-scan-reading")).toBeNull();
    await act(async () => {
      fireEvent.press(view.getByText("chat.math_scan_solve"));
    });
    expect(view.onSolve).not.toHaveBeenCalled();
    await act(async () => {
      fireEvent.press(view.getByText("chat.math_scan_send_photo"));
    });
    expect(view.onSendPhoto).toHaveBeenCalledWith("");
  });

  it("sends the checked reading with the photo", async () => {
    const view = await renderReview({ status: "ready", reading: "x^2 = 9", uncertain: false });
    await act(async () => {
      fireEvent.press(view.getByText("chat.math_scan_send_photo"));
    });
    expect(view.onSendPhoto).toHaveBeenCalledWith("x^2 = 9");
  });

  it("offers the photo and a retake when the read failed", async () => {
    const view = await renderReview({ status: "failed" });
    expect(view.getByText("chat.math_scan_read_failed")).toBeTruthy();
    await act(async () => {
      fireEvent.press(view.getByText("chat.math_scan_solve"));
    });
    expect(view.onSolve).not.toHaveBeenCalled();
    await act(async () => {
      fireEvent.press(view.getByText("chat.math_scan_retake"));
    });
    expect(view.onRetake).toHaveBeenCalled();
  });

  it("does not solve an emptied reading", async () => {
    const view = await renderReview({ status: "ready", reading: "2x = 4", uncertain: false });
    await act(async () => {
      fireEvent.changeText(view.getByTestId("math-scan-reading"), "   ");
    });
    await act(async () => {
      fireEvent.press(view.getByText("chat.math_scan_solve"));
    });
    expect(view.onSolve).not.toHaveBeenCalled();
  });

  // Privacy B9: the read already sent the photo to Recall and on to third-party
  // AI providers, and Send photo sends it again into the chat. The review says so
  // in every state, above the actions, where a screen reader also reaches it first.
  it.each<ScanReadingState>([
    { status: "reading" },
    { status: "ready", reading: "2x + 3 = 7", uncertain: false },
    { status: "failed" },
  ])("says where the photo goes while $status", async (state) => {
    const view = await renderReview(state);
    const line = view.getByText("chat.math_scan_photo_disclosure");
    expect(line.props.maxFontSizeMultiplier).toBe(DYNAMIC_TYPE_MAX);
    const texts = view.getAllByText(/^chat\./).map((node) => node.props.children as string);
    expect(texts.indexOf("chat.math_scan_photo_disclosure")).toBeLessThan(texts.indexOf("chat.math_scan_solve"));
    expect(texts.indexOf("chat.math_scan_photo_disclosure")).toBeLessThan(texts.indexOf("chat.math_scan_send_photo"));
  });
});
