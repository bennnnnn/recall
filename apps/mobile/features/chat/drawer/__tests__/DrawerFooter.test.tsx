import { fireEvent, render } from "@testing-library/react-native";

import { DrawerFooter } from "@/features/chat/drawer/DrawerFooter";
import { makeConversationListStyles } from "@/features/chat/drawer/conversationListStyles";
import { lightTheme } from "@/lib/theme";

jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));

it("puts the app's name and search at the bottom", async () => {
  const onOpenSearch = jest.fn();
  const view = await render(
    <DrawerFooter styles={makeConversationListStyles(lightTheme)} theme={lightTheme}
      paddingBottom={0} onOpenSearch={onOpenSearch} />,
  );

  expect(view.getByText("app.name")).toBeTruthy();
  await fireEvent.press(view.getByRole("button", { name: "search.open_accessibility" }));
  expect(onOpenSearch).toHaveBeenCalledTimes(1);
});
