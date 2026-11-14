/**
 * GFX-02 (2026-11-13 STEM audit): the SMILES and Mermaid drawings are web views a screen
 * reader cannot read, and the function graph's tap area said only "Expand". Each is now
 * labelled from its own spec, in the reader's language.
 */
import { render } from "@testing-library/react-native";
import type { ReactElement } from "react";

import { Chemistry2DView } from "@/components/rich/ChemistryBlock";
import { MermaidBlock } from "@/components/rich/MermaidBlock";
import "@/lib/i18n";

jest.unmock("react-i18next");
jest.mock("expo-file-system/legacy", () => ({}));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("@/lib/preview/previewPageFile", () => ({
  previewPageFile: jest.fn(async () => "file:///cache/preview-pages/page-0123456789abcdef.html"),
  readyPreviewPageFile: jest.fn(() => null),
  forgetPreviewPageFile: jest.fn(),
}));
jest.mock("@/lib/webView", () => {
  const React = jest.requireActual<typeof import("react")>("react");
  const { View } = jest.requireActual<typeof import("react-native")>("react-native");
  function MockWebView() {
    return React.createElement(View, { testID: "preview-webview" });
  }
  return {
    ...jest.requireActual("@/lib/webView"),
    getPreviewWebView: () => ({ mode: "rnc", Component: MockWebView }),
  };
});

it("names a 2D molecule by its name, else its SMILES", async () => {
  const named = await render((<Chemistry2DView smiles="CCO" fence="chemistry" name="Ethanol" />) as ReactElement);
  expect(await named.findByLabelText("2D structure of Ethanol")).toBeTruthy();
  const bare = await render((<Chemistry2DView smiles="CCO" fence="chemistry" />) as ReactElement);
  expect(await bare.findByLabelText("2D structure of CCO")).toBeTruthy();
});

it("says what a Mermaid diagram shows", async () => {
  const view = await render(
    (<MermaidBlock content={"flowchart TD\n  A[Start] --> B{Is it raining?}"} />) as ReactElement,
  );
  expect(await view.findByLabelText("Flowchart showing Start, Is it raining?")).toBeTruthy();
});

it("names a Mermaid diagram by its kind when its source names nothing", async () => {
  const view = await render((<MermaidBlock content={"graph TD\n  A --> B"} />) as ReactElement);
  expect(await view.findByLabelText("Flowchart")).toBeTruthy();
});
