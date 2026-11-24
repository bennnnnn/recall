import { act, fireEvent, render } from "@testing-library/react-native";

import Onboarding from "@/features/auth/screens/OnboardingScreen";
import { SLIDES } from "@/features/auth/components/landing/FeatureShowcase";

const mockCompleteOnboarding = jest.fn(async () => {});
const mockReplace = jest.fn();
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ onboarded: false, completeOnboarding: mockCompleteOnboarding }),
}));
jest.mock("expo-router", () => ({
  Redirect: () => null,
  useRouter: () => ({ replace: mockReplace }),
}));
jest.mock("@/features/billing/model/welcomePlans", () => ({
  offerPlansAfterSignIn: jest.fn(async () => {}),
}));

it("Next turns every slide; Get started shows only on the last and finishes", async () => {
  const screen = await render(<Onboarding />);
  expect(screen.getByText("onboarding.headline")).toBeOnTheScreen();
  expect(screen.queryByText("app.name")).toBeNull();
  for (let slide = 0; slide < SLIDES.length - 1; slide++) {
    expect(screen.queryByText("onboarding.get_started")).toBeNull();
    await act(async () => {
      fireEvent.press(screen.getByText("onboarding.next"));
    });
  }
  expect(screen.queryByText("onboarding.next")).toBeNull();
  await act(async () => {
    fireEvent.press(screen.getByText("onboarding.get_started"));
  });
  expect(mockCompleteOnboarding).toHaveBeenCalledTimes(1);
  expect(mockReplace).toHaveBeenCalledWith("/login");
});
