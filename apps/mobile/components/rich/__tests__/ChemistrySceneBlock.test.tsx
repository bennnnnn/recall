import { render } from "@testing-library/react-native";

import { ChemistrySceneBlock } from "@/components/rich/ChemistrySceneBlock";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

jest.mock("@/lib/theme", () => {
  const actual = jest.requireActual("@/lib/theme");
  return { ...actual, useTheme: () => actual.lightTheme };
});

jest.mock("@/ui/icons/Icon", () => ({ Icon: () => null }));

describe("ChemistrySceneBlock", () => {
  it("draws the verified water angle", async () => {
    const { getByText } = await render(
      <ChemistrySceneBlock
        content={JSON.stringify({
          kind: "vsepr",
          title: "H2O",
          central: "O",
          terminals: ["H", "H"],
          lone_pairs: 2,
          geometry: "bent",
          bond_angle: "104.5°",
          electron_geometry: "tetrahedral",
          ideal_angle: "109.5°",
        })}
      />,
    );
    expect(getByText("104.5°")).toBeTruthy();
    expect(getByText("bent, 2 lone pairs")).toBeTruthy();
    expect(getByText("tetrahedral, ideal 109.5°")).toBeTruthy();
  });

  it("shows the chemistry error note for invalid JSON", async () => {
    const { getByText } = await render(<ChemistrySceneBlock content="{" />);
    expect(getByText("rich.chemistry_invalid")).toBeTruthy();
  });
});
