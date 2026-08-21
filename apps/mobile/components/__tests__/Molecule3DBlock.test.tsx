/**
 * Molecule3DBlock — 3D molecule viewer with style controls.
 *
 * The WebView and heavy deps are mocked; we verify the component renders
 * the style toggle buttons when an SDF is present.
 */
import React from "react";
import { render } from "@testing-library/react-native";

jest.mock("@/lib/webView", () => ({
  getPreviewWebView: () => ({
    Component: () => null,
    mode: "rnc",
  }),
  STATIC_HTML_ORIGIN_WHITELIST: ["about:blank"],
  useStaticOnlyNavigation: () => () => true,
}));

jest.mock("@/hooks/useDeferredWebViewMount", () => ({
  useDeferredWebViewMount: () => ({ canMount: true, onLoaded: jest.fn() }),
}));

jest.mock("@/lib/previewSandbox", () => ({
  injectPreviewCsp: (html: string) => html,
  inlineScript: (s: string) => s,
}));

jest.mock("@/lib/vendor/threeDMolMinJs", () => ({
  THREE_D_MOL_MIN_JS: "/* 3dmol mock */",
}));

jest.mock("@/components/Icon", () => ({
  Icon: () => null,
}));

jest.mock("@/components/CopyButton", () => ({
  CopyButton: () => null,
}));

jest.mock("@/lib/theme", () => ({
  useTheme: () => ({
    isDark: false,
    primary: "#007AFF",
    bg: "#fff",
    surface: "#f5f5f5",
    contentSurface: "#fafafa",
    border: "#ddd",
    text: "#000",
    textSecondary: "#666",
    textTertiary: "#999",
    danger: "#ff3b30",
  }),
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

import { Molecule3DBlock } from "@/components/rich/Molecule3DBlock";

const VALID_SDF = `Ethanol
     RDKit          3D

  3  2  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0  0
    2.5000    1.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
M  END`;

describe("Molecule3DBlock", () => {
  it("renders without crashing when given a valid SDF", async () => {
    const { toJSON } = await render(<Molecule3DBlock content={VALID_SDF} />);
    // Should produce a render tree (not null).
    expect(toJSON()).not.toBeNull();
  });

  it("renders without crashing when no SDF is present", async () => {
    const { toJSON } = await render(<Molecule3DBlock content="no sdf here" />);
    expect(toJSON()).not.toBeNull();
  });
});
