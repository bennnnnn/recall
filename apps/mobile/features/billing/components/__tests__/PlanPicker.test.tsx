import { act, fireEvent, render } from "@testing-library/react-native";

import { AllBenefits, benefitColumns, PlanCard } from "@/features/billing/components/PlanPicker";

const BENEFITS = ["Unlimited chat", "Maths help", "Physics help", "Chemistry help", "Maths calculator", "Image generation"];

describe("benefitColumns", () => {
  it("sets two columns only where the longest line fits half the card whole", () => {
    // A big iPhone's card (~350 wide) fits "Image generation" twice over; a narrow phone's does not.
    expect(benefitColumns(352, BENEFITS)).toBe(2);
    expect(benefitColumns(272, BENEFITS)).toBe(1);
  });

  it("falls to one column for larger text, or a language with longer words", () => {
    expect(benefitColumns(352, BENEFITS, 1.3)).toBe(1);
    expect(benefitColumns(352, ["Calculadora de matemática"])).toBe(1);
  });
});

describe("PlanCard and AllBenefits", () => {
  it("keeps the card to its first two lines", async () => {
    const screen = await render(<PlanCard title="Recall Pro" features={BENEFITS} />);
    expect(screen.getByText("Maths help")).toBeOnTheScreen();
    expect(screen.queryByText("Physics help")).toBeNull();
  });

  it("lists every benefit in the full list, each on one line, cut rather than broken", async () => {
    const screen = await render(<AllBenefits features={BENEFITS} />);
    await act(async () => {
      fireEvent(screen.getByTestId("upgrade-all-benefits-list"), "layout", { nativeEvent: { layout: { width: 272, height: 100, x: 0, y: 0 } } });
    });
    for (const benefit of BENEFITS) expect(screen.getByText(benefit)).toBeOnTheScreen();
    expect(screen.getByText("Unlimited chat").props.numberOfLines).toBe(1);
  });
});
