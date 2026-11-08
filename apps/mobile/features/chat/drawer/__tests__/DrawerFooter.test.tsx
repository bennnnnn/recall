import { StyleSheet } from "react-native";
import { fireEvent, render } from "@testing-library/react-native";

import { DrawerFooter } from "@/features/chat/drawer/DrawerFooter";
import { makeConversationListStyles } from "@/features/chat/drawer/conversationListStyles";
import am from "@/lib/i18n/am.json";
import de from "@/lib/i18n/de.json";
import en from "@/lib/i18n/en.json";
import es from "@/lib/i18n/es.json";
import fr from "@/lib/i18n/fr.json";
import itLocale from "@/lib/i18n/it.json";
import pt from "@/lib/i18n/pt.json";
import ru from "@/lib/i18n/ru.json";
import tr from "@/lib/i18n/tr.json";
import { Space } from "@/lib/space";
import { lightTheme } from "@/lib/theme";

jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));

const props = {
  styles: makeConversationListStyles(lightTheme),
  theme: lightTheme,
  paddingBottom: 30,
  keyboardHeight: 0,
  searchQuery: "",
  searchInputRef: { current: null },
  onSearchChange: jest.fn(),
  onOpenSearch: jest.fn(),
  onCloseSearch: jest.fn(),
};

function footerStyle(view: Awaited<ReturnType<typeof render>>) {
  return StyleSheet.flatten(view.getByTestId("drawer-footer").props.style);
}

it("is one search bar at the bottom that opens search", async () => {
  const onOpenSearch = jest.fn();
  const view = await render(<DrawerFooter {...props} searchOpen={false} onOpenSearch={onOpenSearch} />);

  expect(view.queryByPlaceholderText("search.placeholder")).toBeNull();
  await fireEvent.press(view.getByRole("search", { name: "search.open_accessibility" }));
  expect(onOpenSearch).toHaveBeenCalledTimes(1);
});

// The bar showed "Search messages..." and VoiceOver said "Search conversations".
it.each(Object.entries({ en, am, de, es, fr, it: itLocale, pt, ru, tr }))(
  "is labelled with the words it shows in %s",
  (_code, bundle) => {
    expect(bundle["search.placeholder"]).toBe(`${bundle["search.open_accessibility"]}…`);
  },
);

it("becomes the field in place, sitting on the keyboard", async () => {
  const onCloseSearch = jest.fn();
  const view = await render(
    <DrawerFooter {...props} searchOpen keyboardHeight={300} onCloseSearch={onCloseSearch} />,
  );

  expect(view.getByPlaceholderText("search.placeholder")).toBeTruthy();
  expect(footerStyle(view)).toMatchObject({ bottom: 300, paddingBottom: Space.xs });
  await fireEvent.press(view.getByRole("button", { name: "common.cancel" }));
  expect(onCloseSearch).toHaveBeenCalledTimes(1);
});

it("rests on the home indicator when the keyboard is down", async () => {
  const view = await render(<DrawerFooter {...props} searchOpen keyboardHeight={0} />);
  expect(footerStyle(view)).toMatchObject({ bottom: 0, paddingBottom: 30 });
});
