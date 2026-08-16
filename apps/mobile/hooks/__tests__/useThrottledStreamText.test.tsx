import React from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";

import { useThrottledStreamText } from "@/hooks/useThrottledStreamText";
import { STREAM_UI_INTERVAL_MS } from "@/lib/streamUiTiming";

function Probe({ value, generating }: { value?: string; generating: boolean }) {
  const shown = useThrottledStreamText(value, generating);
  return <Text>{shown ?? ""}</Text>;
}

describe("useThrottledStreamText", () => {
  afterEach(() => {
    jest.useRealTimers();
  });

  it("flushes immediately when generation ends", async () => {
    const view = await act(async () => render(<Probe value="draft" generating />));
    await act(async () => {
      view.rerender(<Probe value="final" generating={false} />);
    });
    expect(view.getByText("final")).toBeTruthy();
  });

  it("holds mid-stream updates until the shared interval", async () => {
    jest.useFakeTimers();
    const view = await act(async () => render(<Probe value="one" generating />));
    expect(view.getByText("one")).toBeTruthy();

    await act(async () => {
      view.rerender(<Probe value="two" generating />);
    });
    expect(view.queryByText("two")).toBeNull();
    expect(view.getByText("one")).toBeTruthy();

    await act(async () => {
      jest.advanceTimersByTime(STREAM_UI_INTERVAL_MS);
    });
    expect(view.getByText("two")).toBeTruthy();
  });
});
