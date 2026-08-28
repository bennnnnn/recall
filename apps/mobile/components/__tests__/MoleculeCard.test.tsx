/**
 * MoleculeCard — one header, 2D default, optional 3D toggle; copy SMILES.
 */
import React from "react";
import { render } from "@testing-library/react-native";

jest.mock("@/components/Icon", () => ({
  Icon: () => null,
}));

jest.mock("@/components/CopyButton", () => {
  const { Text } = jest.requireActual("react-native");
  return {
    CopyButton: ({ text }: { text: string }) => <Text testID="copy-payload">{text}</Text>,
  };
});

jest.mock("@/lib/theme", () => ({
  useTheme: () => ({
    isDark: false,
    primary: "#007AFF",
    onPrimary: "#FFFFFF",
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

import { MoleculeCard } from "@/components/rich/MoleculeCard";

const VALID_SDF = `Ethanol
     RDKit          3D

  3  2  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0  0
    2.5000    1.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
M  END`;

describe("MoleculeCard", () => {
  it("shows one header, 2D by default, and copies SMILES not SDF", async () => {
    const content = JSON.stringify({
      smiles: "CCO",
      caption: "Ethanol",
      sdf: VALID_SDF,
    });
    const { getByText, getAllByText, getByTestId, queryByText } = await render(
      <MoleculeCard content={content} />,
    );
    expect(getAllByText("rich.chemistry_structure")).toHaveLength(1);
    expect(getByText("Ethanol")).toBeTruthy();
    expect(getByText("rich.chemistry_dev_build")).toBeTruthy();
    expect(getByText("rich.chemistry_2d")).toBeTruthy();
    expect(getByText("rich.chemistry_3d")).toBeTruthy();
    expect(queryByText("Ball")).toBeNull();
    expect(getByTestId("copy-payload").props.children).toBe("CCO");
    expect(String(getByTestId("copy-payload").props.children)).not.toContain("V2000");
  });

  it("shows a 3D toggle when SDF is present and stays on 2D until chosen", async () => {
    const content = JSON.stringify({ smiles: "CCO", sdf: VALID_SDF });
    const { getByText, getAllByText, getByTestId, queryByText } = await render(
      <MoleculeCard content={content} />,
    );
    expect(getAllByText("rich.chemistry_structure")).toHaveLength(1);
    expect(getByTestId("molecule-mode-2d").props.accessibilityState).toEqual({ selected: true });
    expect(getByTestId("molecule-mode-3d").props.accessibilityState).toEqual({ selected: false });
    expect(getByText("rich.chemistry_dev_build")).toBeTruthy();
    expect(queryByText("Ball")).toBeNull();
    expect(getByTestId("copy-payload").props.children).toBe("CCO");
  });

  it("hides the 3D toggle when there is no SDF", async () => {
    const { getAllByText, queryByText } = await render(
      <MoleculeCard content={JSON.stringify({ smiles: "CCO" })} />,
    );
    expect(getAllByText("CCO").length).toBeGreaterThan(0);
    expect(queryByText("rich.chemistry_3d")).toBeNull();
    expect(queryByText("Ball")).toBeNull();
  });

  it("renders an invalid-structure hint when SMILES is missing", async () => {
    const { getByText } = await render(<MoleculeCard content="not a molecule" />);
    expect(getByText("rich.chemistry_invalid")).toBeTruthy();
  });
});
