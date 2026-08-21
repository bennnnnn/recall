import { fireEvent, render } from "@testing-library/react-native";

import { ChatInlineError } from "@/components/chat/ChatInlineError";

jest.mock("@/components/Icon", () => ({
  Icon: () => null,
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) =>
      ({
        "common.retry": "Retry",
        "settings.model": "Models",
        "chat.error_dismiss_a11y": "Dismiss error",
      })[key] ?? key,
  }),
}));

jest.mock("@/lib/theme", () => ({
  useTheme: () => ({
    isDark: false,
    surface: "#fff",
    warning: "#f90",
    text: "#111",
    primary: "#36f",
    onPrimary: "#fff",
    textTertiary: "#777",
  }),
}));

describe("ChatInlineError", () => {
  it("offers one-tap retry for a failed reply", async () => {
    const onRetry = jest.fn();
    const view = await render(
      <ChatInlineError
        error={{ kind: "generic", message: "Connection lost. Try again." }}
        onRetry={onRetry}
        onDismiss={jest.fn()}
        bottom={20}
      />,
    );

    fireEvent.press(view.getByTestId("chat-error-retry"));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("opens model selection when the active model is unavailable", async () => {
    const onChangeModel = jest.fn();
    const view = await render(
      <ChatInlineError
        error={{ kind: "model_unavailable", message: "Pick a different model." }}
        onChangeModel={onChangeModel}
        onDismiss={jest.fn()}
        bottom={20}
      />,
    );

    fireEvent.press(view.getByTestId("chat-error-change-model"));
    expect(onChangeModel).toHaveBeenCalledTimes(1);
  });
});
